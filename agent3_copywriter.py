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
    _aguardando_copy.clear()


def set_copy_decision(decision: str):
    """Chamado pelo scheduler.py quando usuario clica em aprovar ou refazer."""
    global _copy_decision
    _copy_decision = decision
    _aguardando_copy.set()


COPY_STRATEGY_BASE = """
REGRAS ABSOLUTAS DE ESCRITA (valem para todos os templates):

CAPITALIZACAO:
- Apenas primeira letra da frase em maiusculo. NUNCA title case.

VOLUME:
- Titulo: 4 a 7 palavras
- Corpo: maximo 35-40 palavras por slide
- Slide 1 (capa): corpo vazio "" - so titulo

CONTINUIDADE:
- Cada slide termina com tensao que puxa pro proximo
"""

COPY_STRATEGY_POR_TEMPLATE = {
    "A": """
TOM DO TEMPLATE A (Cinematico):
- Jornalistico, denso, investigativo. Reportagem de revista de negocios.
- Afirma fenomenos com peso. Usa dados e nomes de empresas reais.
- Ritmo: 2 frases curtas (socos) + 1 frase longa (ancoragem)
- NUNCA coach motivacional. NUNCA "aprenda a", "dica", "passo a passo".

ESTRUTURA:
1. CAPA - manchete forte, factual, provoca curiosidade
2. CONTEXTO - dado concreto + contextualizacao de mercado
3. PROVA - amplificacao com evidencia real
4. DIAGNOSTICO - causa raiz, frase curta e precisa
5. VIRADA - alternativa/contraponto com dado
6. MECANISMO - como funciona na pratica
7. APROFUNDAMENTO - nova perspectiva, camada extra
8. PROVA CIENTIFICA - sem imagem, ancora logica
9. CONCLUSAO - verdade maior, peso jornalistico
10. CTA - conversacional, nao agressivo
""",
    "B": """
TOM DO TEMPLATE B (Feed Claro):
- Acessivel, didatico, proximo. Como um especialista amigo explicando.
- Linguagem direta e pratica. Cada slide = uma ideia clara e aplicavel.
- Ritmo: frases medias, fluidas. Pode usar listas mentais (sem bullet literal).
- Conectado ao cotidiano. Usa exemplos do dia a dia de quem faz marketing/negocios.

ESTRUTURA:
1. CAPA - afirmacao que quebra crenca comum
2. PROBLEMA - o que a maioria faz de errado
3. POR QUE - a razao real por tras do problema
4. DADOS - numeros que provam o problema
5. VIRADA - o que funciona de verdade
6. COMO - o mecanismo pratico
7. EXEMPLO - case ou situacao real
8. PROVA - sem imagem, dado que confirma
9. INSIGHT - a sacada que muda a perspectiva
10. CTA - convite natural, proximo, sem pressao
""",
    "C": """
TOM DO TEMPLATE C (Editorial Escuro):
- Filosofico, provocativo, denso. Verdades que incomodam.
- Frases curtas com peso. Cada frase deve cortar.
- Ritmo: frases curtas e medias. NUNCA longas demais. Silencio entre ideias.
- Sem explicacoes em excesso. A frase faz o trabalho sozinha.
- Pode ser duro, direto, sem suavizar.

ESTRUTURA:
1. CAPA - afirmacao que provoca ou assusta
2. DIAGNOSTICO - a raiz do problema em poucas palavras
3. CONTRAINTUITIVO - o que todos acreditam que esta errado
4. EVIDENCIA - dado ou caso que prova
5. VIRADA - a mudanca de perspectiva
6. MECANISMO - por que a maioria nao ve
7. APROFUNDAMENTO - o custo de ignorar isso
8. PROVA - sem imagem, a ancora logica
9. VERDADE - a conclusao que pesa
10. CTA - um convite simples, quase sussurrado
"""
}


def get_copy_strategy(template: str) -> str:
    base = COPY_STRATEGY_BASE
    especifico = COPY_STRATEGY_POR_TEMPLATE.get(template, COPY_STRATEGY_POR_TEMPLATE["A"])
    return base + especifico


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


async def generate_copy_with_claude(trend: dict, angulo: dict, template: str = "A") -> dict:
    """Gera a copy completa dos 10 slides com tom alinhado ao template escolhido."""
    print("   Pesquisando dados reais...")
    dados_pesquisa = await asyncio.to_thread(research_topic, trend, angulo)
    dados_section = ""
    if dados_pesquisa:
        dados_section = f"\nDADOS REAIS PESQUISADOS (use como ancora de credibilidade):\n{dados_pesquisa}\n"

    # Aguarda 15s para evitar rate limit entre pesquisa e geracao da copy
    print("   Aguardando 15s para evitar rate limit...")
    await asyncio.sleep(15)

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

    # Pega estrategia de copy do template escolhido
    copy_strategy = get_copy_strategy(template)
    template_nomes = {"A": "Cinematico", "B": "Feed Claro", "C": "Editorial Escuro"}
    template_nome = template_nomes.get(template, "Cinematico")

    # Retry com backoff em caso de rate limit
    for tentativa in range(3):
        prompt_content = f"""Voce e o Copywriter da Wavy - agencia de marketing digital brasileira.
Publico: empreendedores, donos de negocio e gestores de marketing brasileiros.

TEMPLATE VISUAL: {template} - {template_nome}
A copy deve ser escrita com o tom e estilo exato deste template.

{copy_strategy}

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

REGRA ESPECIAL SLIDE 1 (CAPA):
- "titulo_bold": manchete forte, 4-7 palavras, impacto maximo - e o unico texto visivel
- "corpo": deixe como string vazia "" - a capa nao tem corpo, so titulo
- "prompt_imagem": imagem cinematografica de fundo que reforce o tema

Retorne APENAS JSON valido neste formato:
{{"slides": [
  {{"slide": 1, "titulo_bold": "...", "corpo": "", "prompt_imagem": "..."}},
  {{"slide": 2, "titulo_bold": "...", "corpo": "...", "prompt_imagem": "..."}},
  ...
]}}"""
        try:
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt_content}]
            )
            break  # sucesso, sai do retry
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                espera = 30 * (tentativa + 1)
                print(f"   Rate limit! Aguardando {espera}s antes de tentar novamente...")
                await asyncio.sleep(espera)
                if tentativa == 2:
                    print("   Rate limit persistente, retornando vazio")
                    return {}
            else:
                print(f"   Erro na chamada Claude: {e}")
                return {}

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

    template = final_choice.get("template", "A")
    template_nomes = {"A": "Cinematico", "B": "Feed Claro", "C": "Editorial Escuro"}
    print(f"Template: {template} - {template_nomes.get(template, 'A')}")

    copy_data = None
    attempts  = 0

    while True:
        attempts += 1
        reset_copywriter()

        print(f"Gerando copy (tentativa {attempts})...")
        copy_data = await generate_copy_with_claude(trend, angulo, template)

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
        "trend":    trend,
        "angulo":   angulo,
        "copy":     copy_data,
        "template": template,
        "formato":  angulo.get("formato", "carrossel")
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
