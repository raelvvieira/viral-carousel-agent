"""
AGENTE 3 - COPYWRITER
Recebe o angulo aprovado, pesquisa dados reais, gera copy completa,
envia pro Telegram para aprovacao. Scheduler gerencia os callbacks.
"""

import os
import json
import asyncio
from anthropic import Anthropic
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = int(os.getenv("TELEGRAM_CHAT_ID"))

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Evento global - scheduler.py seta quando usuario clica em aprovar/refazer
_copy_decision = None  # "approve" ou "redo"
_aguardando_copy = asyncio.Event()


def reset_copywriter():
    global _copy_decision, _aguardando_copy
    _copy_decision = None
    _aguardando_copy = asyncio.Event()


def set_copy_decision(decision: str):
    """Chamado pelo scheduler.py quando usuario clica em aprovar ou refazer."""
    global _copy_decision
    _copy_decision = decision
    _aguardando_copy.set()


COPY_STRATEGY = """
ESTRATEGIA DE COPY - CARROSSEL (Estilo Editorial Wavy)

REGRAS ABSOLUTAS:

CAPITALIZACAO:
- Apenas primeira letra da frase em maiusculo. NUNCA title case.
- ERRADO: "O Mercado Esta Mudando Rapido"
- CORRETO: "O mercado esta mudando rapido"

RITMO:
- Padrao ouro: 2 frases curtas (socos) + 1 frase longa (ancoragem)
- Exemplo: "Nao e ruido. E fadiga estrutural. A geracao que cresceu online esta cansada de gamificar afeto."
- NUNCA 4+ frases curtas seguidas

VOLUME:
- Titulo: 4 a 7 palavras
- Corpo: maximo 35-40 palavras por slide

TOM:
- Jornalistico-editorial. NUNCA coach motivacional.
- Afirma fenomenos. Nao aconselha.
- NUNCA: "voce precisa", "aprenda a", "dica", "passo a passo"

ESTRUTURA DOS 10 SLIDES:
1. CAPA - pergunta ou afirmacao que para o scroll (manchete jornalistica)
2. PROBLEMA - dado concreto + contextualizacao
3. PROVA - amplificacao com evidencia
4. DIAGNOSTICO - causa raiz, frase curta e precisa
5. VIRADA - alternativa/contraponto com dado
6. MECANISMO - por que funciona (insight psicologico)
7. APROFUNDAMENTO - camada extra, nova perspectiva
8. PROVA CIENTIFICA - sem imagem, ancora logica/cientifica
9. CONCLUSAO FILOSOFICA - fundo escuro, verdade maior
10. CTA - conversacional, nunca imperativo agressivo
"""


def research_topic(trend: dict, angulo: dict) -> str:
    """Pesquisa dados reais sobre o tema antes de gerar a copy."""
    query = f"{angulo.get('titulo', trend.get('titulo', ''))} {trend.get('topico', '')} marketing 2025 2026 dados pesquisa"
    print(f"   Pesquisando: {query}")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": f"""Pesquise dados concretos sobre esse tema para embasar um carrossel de marketing:

Tema: {angulo.get('titulo', trend.get('titulo', ''))}
Topico: {trend.get('topico', '')}
Descricao: {trend.get('descricao', '')}

Busque numeros, percentuais, estatisticas recentes, casos reais, dados de pesquisas.
Retorne apenas os dados mais relevantes em formato de lista. Sem analise, so os fatos."""}]
        )
        resultado = []
        for block in response.content:
            if hasattr(block, "text") and block.text:
                resultado.append(block.text)
        pesquisa = "\n".join(resultado).strip()
        print(f"   Pesquisa concluida: {len(pesquisa)} caracteres")
        return pesquisa
    except Exception as e:
        print(f"   Pesquisa falhou: {e}")
        return ""


def generate_copy_with_claude(trend: dict, angulo: dict) -> dict:
    """Gera a copy completa dos 10 slides."""
    print("   Pesquisando dados reais...")
    dados_pesquisa = research_topic(trend, angulo)
    dados_section = ""
    if dados_pesquisa:
        dados_section = f"\nDADOS REAIS PESQUISADOS (use como ancora de credibilidade):\n{dados_pesquisa}\n"

    # Carrega referencias de inspiracao
    inspiracoes_txt = ""
    try:
        with open("/tmp/wavy_inspiracoes.json", "r", encoding="utf-8") as f:
            refs = json.load(f)
        if refs:
            inspiracoes_txt = "\nREFERENCIAS DE ESTILO (carrosseis reais enviados como inspiracao):\n"
            for i, r in enumerate(refs[-3:], 1):
                inspiracoes_txt += f"\nReferencia {i} ({r.get('data', '')}):\n{r.get('texto', '')}\n"
            inspiracoes_txt += "\nUse o tom, ritmo e estrutura dessas referencias como modelo."
    except Exception:
        pass

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": f"""Voce e o Copywriter da Wavy - agencia de marketing digital brasileira.
Estilo: jornalistico-editorial, cinematografico, inteligente. NUNCA coach motivacional.
Referencia: Leo Baltazar, Caio Carneiro.
Publico: empreendedores e gestores de marketing digital brasileiros.

{COPY_STRATEGY}

{dados_section}

TREND:
- Titulo: {trend['titulo']}
- Descricao: {trend['descricao']}
- Topico: {trend['topico']}

ANGULO ESCOLHIDO:
- Titulo: {angulo['titulo']}
- Hook: {angulo['hook']}
- Emocao dominante: {angulo['emocao']}
- Perfil alvo: {angulo['perfil_alvo']}

{inspiracoes_txt}

Escreva a copy completa dos 10 slides. Para cada slide retorne:
- "slide": numero (1-10)
- "titulo_bold": titulo principal, max 7 palavras, so primeira letra maiuscula
- "corpo": corpo do texto, max 35-40 palavras, padrao 2 frases curtas + 1 longa
- "prompt_imagem": descricao em ingles para imagem cinematografica no Freepik (slides 1-7 e 10 tem imagem; slides 8 e 9 nao tem)

Retorne APENAS JSON valido neste formato:
{{"slides": [
  {{"slide": 1, "titulo_bold": "...", "corpo": "...", "prompt_imagem": "..."}},
  {{"slide": 2, "titulo_bold": "...", "corpo": "...", "prompt_imagem": "..."}},
  ...
]}}"""}]
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return {"slides": parsed}
        return parsed
    except Exception as e:
        print(f"Erro ao parsear copy: {e}")
        print(f"Raw: {response.content[0].text[:300]}")
        return {}


async def send_copy_to_telegram(copy_data: dict, angulo: dict):
    """Envia a copy pro Telegram slide por slide com botoes de aprovacao."""
    bot    = Bot(token=TELEGRAM_TOKEN)
    slides = copy_data.get("slides", [])

    # Cabecalho
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"Copy do carrossel gerada!\n\n{angulo['titulo']}\n{len(slides)} slides\n\nRevisando cada slide abaixo:",
        parse_mode=None
    )

    # Envia cada slide separado
    for slide in slides:
        n      = slide.get("slide", "")
        titulo = slide.get("titulo_bold", "")
        corpo  = slide.get("corpo", "")
        prompt = slide.get("prompt_imagem", "")

        texto = f"Slide {n}/10\n\nTitulo: {titulo}\n\nCorpo: {corpo}"
        if prompt:
            texto += f"\n\nImagem: {prompt}"

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=texto,
            parse_mode=None
        )

    # Botoes de aprovacao
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Aprovar e gerar artes", callback_data="copy_approve"),
        InlineKeyboardButton("Refazer copy", callback_data="copy_redo")
    ]])

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="Aprovar essa copy ou refazer?",
        reply_markup=keyboard
    )


async def run_copywriter(final_choice: dict) -> dict:
    """
    Funcao principal do Agente 3.
    final_choice deve ter: "trend", "angulo", "formato"
    """
    global _copy_decision

    # Suporta tanto "angulo" (novo) quanto "angulo_escolhido" (legado)
    trend  = final_choice.get("trend", {})
    angulo = final_choice.get("angulo") or final_choice.get("angulo_escolhido", {})

    print(f"Agente 3 - Copywriter iniciado")
    print(f"Trend: {trend.get('titulo', '')}")
    print(f"Angulo: {angulo.get('titulo', '')}")

    copy_data = None
    attempts  = 0

    while True:
        attempts += 1
        reset_copywriter()

        print(f"Gerando copy (tentativa {attempts})...")
        copy_data = generate_copy_with_claude(trend, angulo)

        if not copy_data or not copy_data.get("slides"):
            print("Copy vazia, tentando novamente...")
            continue

        print(f"Copy gerada: {len(copy_data.get('slides', []))} slides")

        # Envia pro Telegram
        await send_copy_to_telegram(copy_data, angulo)
        print("Copy enviada. Aguardando aprovacao no Telegram...")

        # Aguarda decisao do usuario (timeout 15 minutos)
        try:
            await asyncio.wait_for(_aguardando_copy.wait(), timeout=900)
        except asyncio.TimeoutError:
            print("Timeout: nenhuma decisao em 15 minutos, aprovando automaticamente")
            _copy_decision = "approve"

        if _copy_decision == "approve":
            break
        else:
            print("Refazendo copy...")

    final_output = {
        "trend": trend,
        "angulo": angulo,
        "copy": copy_data,
        "formato": angulo.get("formato", "carrossel")
    }

    with open("/tmp/copy_result.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    print(f"Copy aprovada apos {attempts} tentativa(s)")
    return final_output


if __name__ == "__main__":
    try:
        with open("/tmp/final_choice.json", "r", encoding="utf-8") as f:
            final_choice = json.load(f)
    except FileNotFoundError:
        print("Rode o agent2_strategist.py primeiro.")
        exit(1)
    result = asyncio.run(run_copywriter(final_choice))
    print(f"Copy pronta: {result['formato']}")
