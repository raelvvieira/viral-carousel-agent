"""
AGENTE 3 — COPYWRITER
Recebe o ângulo aprovado e escreve a copy completa
seguindo a estratégia de copy da Wavy (Estilo 1 e Estilo 2).
Envia pro Telegram para aprovação antes de passar ao Designer.
"""

import os
import json
import asyncio
from anthropic import Anthropic
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

# ─── CONFIGURAÇÕES ───────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = int(os.getenv("TELEGRAM_CHAT_ID"))

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── ESTRATÉGIA DE COPY ──────────────────────────────────────────

COPY_STRATEGY_CAROUSEL = """
ESTRATÉGIA DE COPY — CARROSSEL (Estilo Editorial Wavy)

REFERÊNCIA DE ESTILO: Leo Baltazar, Caio Carneiro, conteúdo editorial de marketing viral brasileiro.

━━━━━━━━━━━━━━━━
REGRAS DE ESCRITA — ABSOLUTAS
━━━━━━━━━━━━━━━━

CAPITALIZAÇÃO:
- Apenas a primeira letra da frase em maiúsculo
- NUNCA title case ("O Amor Virou Algoritmo" está ERRADO)
- CORRETO: "O amor virou algoritmo."
- Nomes próprios, siglas e marcas mantêm capitalização normal

PONTUAÇÃO E RITMO:
- Ponto final cria respiração — use com intenção, não como lista
- Padrão de ouro: 2 frases curtas (socos) + 1 frase longa (ancoragem)
- Exemplo: "Não é ruído. É fadiga estrutural. A geração que cresceu online está cansada de gamificar afeto."
- NUNCA sequências de 4+ frases curtas seguidas — vira telegrama
- Vírgula para listar, ponto para respirar, travessão para contrastar

VOLUME DE TEXTO:
- Título: 4 a 7 palavras. Nunca mais de uma linha visual.
- Corpo: 2 a 4 frases. Máximo 35-40 palavras.
- Se precisar de mais palavras, o argumento está frouxo — corte, não expanda

TOM E VOZ:
- Jornalístico-editorial. Nunca coach motivacional.
- Afirma fenômenos. Não aconselha o leitor diretamente.
- Usa "a geração", "o mercado", "as marcas" — fala sobre o mundo, não para o leitor
- Dados concretos como âncora: percentuais, números, fatos verificáveis
- Metáforas simples e precisas: "gamificar afeto", "cards descartáveis", "química real"
- NUNCA: "você precisa", "aprenda a", "descubra como", "dica", "passo a passo"

CONTINUIDADE ENTRE SLIDES:
- Cada slide termina com tensão aberta que puxa para o próximo
- É uma corrente lógica, não slides independentes
- Estrutura: Problema → Prova → Diagnóstico → Virada → Por que funciona → Conclusão filosófica

━━━━━━━━━━━━━━━━
ESTRUTURA DOS 10 SLIDES
━━━━━━━━━━━━━━━━

Slide 1 — CAPA (Pergunta ou afirmação que para o scroll)
- Pode ser pergunta direta ("Por que X está fazendo Y?") ou afirmação contraintuitiva
- Precisa criar lacuna mental: o leitor PRECISA virar para fechar a história
- Tom jornalístico — como manchete de revista de negócios
- Exemplo: "Por que a geração Z está deletando o Tinder para encontrar amor em clubes de corrida."

Slide 2 — PROBLEMA (Dado + contextualização)
- Abre com dado concreto ou fato verificável no título
- Corpo contextualiza o problema com profundidade
- Termina com diagnóstico que abre tensão para o próximo slide
- Exemplo título: "O Tinder perdeu milhões de usuários nos últimos anos."

Slide 3 — PROVA (Amplificação do problema)
- Outro dado ou evidência que confirma e amplifica o problema
- Mostra que não é caso isolado — é tendência
- Exemplo título: "79% dos jovens relatam burnout com apps de namoro."

Slide 4 — DIAGNÓSTICO (O porquê profundo)
- Explica a causa raiz do problema
- Revela algo que o leitor não havia considerado
- Frase curta e precisa no título — máximo 5 palavras
- Exemplo título: "O amor virou algoritmo."

Slide 5 — VIRADA (A alternativa surge)
- Apresenta o contraponto, a nova tendência, o movimento oposto
- Usa dado para ancorar a virada
- Exemplo título: "Enquanto isso, os clubes explodem."

Slide 6 — MECANISMO (Por que funciona)
- Explica o mecanismo por trás da virada
- Insight emocional ou psicológico
- Exemplo título: "Sofrer juntos cria vínculo."

Slide 7 — APROFUNDAMENTO (Camada extra)
- Adiciona outra dimensão ao argumento
- Expande o insight com nova perspectiva
- Exemplo título: "A academia virou o novo bar."

Slide 8 — PROVA CIENTÍFICA (Sem imagem — só texto)
- Âncora lógica/científica para o argumento emocional dos slides anteriores
- Dados, neurociência, pesquisa, lógica irrefutável
- Reduz ceticismo — sem isso vira só opinião bem escrita
- Exemplo título: "Endorfina > algoritmo."

Slide 9 — CONCLUSÃO FILOSÓFICA (Fundo escuro)
- Eleva o argumento para uma verdade maior
- Deixa o leitor com reflexão, não com resposta
- Tom: observação inteligente sobre o mundo
- Exemplo título: "Não é sobre namoro. É sobre autenticidade."

Slide 10 — CTA (Conversacional — sem imperativo agressivo)
- Tom de conversa, não de ordem
- Pode usar primeira pessoa ("Vai por mim...")
- Pede ação simples: seguir, comentar, salvar
- NUNCA: "E aí, gostou?", "Me conta nos comentários!", "Compartilhe se fez sentido"
- Exemplo: "Vai por mim, essa conta não vai aparecer de novo... Então já toca em seguir para receber mais conteúdos como esse."
"""

COPY_STRATEGY_REELS = """
ESTRATÉGIA DE COPY — REELS (Wavy)

ESTRUTURA (0–30s):

0–3s — HOOK (Interrupção brutal)
- Afirmação que quebra padrão imediatamente
- Tipos: "A verdade sobre X", "Você está fazendo X errado", "O que NUNCA...", Inversão, Curiosidade extrema
- Objetivo: criar lacuna mental impossível de ignorar

3–10s — CURIOSIDADE PROGRESSIVA
- Mantém tensão sem entregar tudo
- Pequenas revelações que deixam algo pendente
- "E o motivo é mais simples do que você imagina"

10–20s — RECOMPENSA EMOCIONAL (Clímax)
- Ativa uma das 5 emoções virais: Indignação, Admiração, Surpresa, Identificação, Medo leve
- Estrutura: Hook → Construção → Clímax
- Ativa dor + identificação + autoridade simultaneamente

20–30s — LOOP + CTA INVISÍVEL
- NÃO termina com "me siga para mais"
- Termina com: Pergunta aberta, Provocação, Parte 2 implícita, Frase inacabada
- Objetivo: fazer o cérebro querer rever o vídeo

REGRAS:
- Clareza brutal — direto, cortado, impactante
- Emoção > Informação
- Polarização controlada (divide opiniões = mais comentários)
- Vulnerabilidade gera autoridade ("Eu já cometi esse erro")
- NUNCA diz "Eu sou especialista" — MOSTRA com história
"""


# ─── GERAR COPY COM CLAUDE ───────────────────────────────────────

def research_topic(trend: dict, angulo: dict) -> str:
    """Pesquisa dados reais sobre o tema na internet antes de gerar a copy."""
    query = f"{angulo.get('titulo', trend.get('titulo', ''))} {trend.get('topico', '')} marketing 2025 2026 dados pesquisa"

    print(f"   🔎 Pesquisando: {query}")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": f"""Pesquise dados concretos sobre esse tema para embasar um carrossel de marketing:

Tema: {angulo.get('titulo', trend.get('titulo', ''))}
Tópico: {trend.get('topico', '')}
Descrição: {trend.get('descricao', '')}

Busque:
- Números, percentuais, estatísticas recentes
- Casos reais de empresas ou mercados
- Dados de pesquisas ou estudos
- Exemplos concretos do Brasil ou global
- Fatos verificáveis que podem ser usados como âncora de credibilidade

Retorne apenas os dados mais relevantes e concretos encontrados, em formato de lista. Sem análise, só os fatos."""
            }]
        )

        # Extrai texto de todas as respostas
        resultado = []
        for block in response.content:
            if hasattr(block, "text") and block.text:
                resultado.append(block.text)

        pesquisa = "
".join(resultado).strip()
        print(f"   ✅ Pesquisa concluída — {len(pesquisa)} caracteres")
        return pesquisa

    except Exception as e:
        print(f"   ⚠️ Pesquisa falhou: {e} — continuando sem dados extras")
        return ""


def generate_copy_with_claude(trend: dict, angulo: dict) -> dict:
    """Pesquisa o tema na internet e gera a copy completa seguindo a estratégia da Wavy."""

    formato = angulo.get("formato", "carrossel")
    strategy = COPY_STRATEGY_CAROUSEL if formato == "carrossel" else COPY_STRATEGY_REELS

    # Pesquisa dados reais antes de gerar
    print("   🌐 Pesquisando dados reais sobre o tema...")
    dados_pesquisa = research_topic(trend, angulo)
    dados_section = ""
    if dados_pesquisa:
        dados_section = f"""
DADOS REAIS PESQUISADOS (use como âncora de credibilidade nos slides):
{dados_pesquisa}

"""

    formato = angulo.get("formato", "carrossel")
    strategy = COPY_STRATEGY_CAROUSEL if formato == "carrossel" else COPY_STRATEGY_REELS

    if formato == "carrossel":
        instruction = """
Escreva a copy completa dos 10 slides do carrossel.
Para cada slide retorne:
- "slide": número do slide (1-10)
- "titulo_bold": texto em negrito (título principal do slide) — máximo 7 palavras, só primeira letra maiúscula
- "corpo": texto do corpo — máximo 3 linhas, 35-40 palavras, padrão 2 frases curtas + 1 longa
- "prompt_imagem": descrição em inglês para gerar imagem cinematográfica no Freepik (slides 1-7 e 10 têm imagem)

Slides sem imagem: slide 8 (só texto) e slide 9 (fundo escuro, só texto).
Slide 10: CTA conversacional, tom de conversa, inclui "palavra_cta" para comentário.

PROFUNDIDADE (diretriz geral):
- Use os dados pesquisados onde fizerem sentido narrativo — não force número em todo slide
- O objetivo é que o carrossel como um todo tenha densidade: dados, casos reais, lógica irrefutável distribuídos naturalmente
- Cada slide deve conter algo que o leitor não sabia ou não havia conectado — nunca o óbvio
- Deixe o tema guiar onde entra dado e onde entra insight emocional
"""
    else:
        instruction = """
Escreva o script completo do Reels.
Retorne:
- "hook": frase de abertura (0-3s)
- "desenvolvimento": blocos de 1-2 frases cada (3-20s) — liste como array
- "climax": frase do clímax emocional (15-20s)
- "cta_final": frase final provocativa sem "me siga" (20-30s)
- "prompt_imagem_capa": descrição em inglês para gerar thumbnail cinematográfica no Freepik
- "legenda_instagram": legenda completa pra postar junto com o reels
"""

    # Carrega referências de inspiração salvas via /inspiracao
    inspiracoes_txt = ""
    try:
        import json as _json
        with open("/tmp/wavy_inspiracoes.json", "r", encoding="utf-8") as _f:
            refs = _json.load(_f)
        if refs:
            inspiracoes_txt = "

REFERÊNCIAS DE ESTILO (carrosséis reais enviados como inspiração):
"
            for i, r in enumerate(refs[-3:], 1):  # usa as 3 mais recentes
                inspiracoes_txt += f"
Referência {i} ({r.get("data", "")}):
{r.get("texto", "")}
"
            inspiracoes_txt += "
Use o tom, ritmo e estrutura dessas referências como modelo."
    except Exception:
        pass

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": f"""Você é o Copywriter da Wavy — agência de marketing digital brasileira.
Seu estilo é jornalístico-editorial, cinematográfico, inteligente. NUNCA coach motivacional, NUNCA lista de dicas.
Referência de estilo: Leo Baltazar, Caio Carneiro — conteúdo editorial viral sobre negócios e marketing.
Público: empreendedores e gestores de marketing digital brasileiros.

REGRAS ABSOLUTAS DE ESCRITA:
1. CAPITALIZAÇÃO: apenas primeira letra da frase em maiúsculo. NUNCA title case.
   ERRADO: "O Mercado Está Mudando Rápido"
   CORRETO: "O mercado está mudando rápido"
2. RITMO: padrão ouro = 2 frases curtas (socos) + 1 frase longa (ancoragem). Nunca 4+ frases curtas seguidas.
   Exemplo: "Não é ruído. É fadiga estrutural. A geração que cresceu online está cansada de gamificar afeto."
3. VOLUME: título 4-7 palavras. Corpo máximo 35-40 palavras por slide.
4. TOM: afirma fenômenos, não aconselha. Usa "o mercado", "as marcas", "a geração" — nunca "você deve" ou "aprenda a".
5. CONTINUIDADE: cada slide termina com tensão aberta que puxa para o próximo. É uma corrente lógica, não slides isolados.

PROFUNDIDADE — REGRA CENTRAL:
- Cada carrossel precisa ter no mínimo 3 dados concretos distribuídos nos slides (percentuais, números, pesquisas, casos reais)
- Dados âncora a credibilidade — sem dado, vira opinião. Com dado, vira jornalismo.
- Use os DADOS REAIS PESQUISADOS fornecidos. Se não houver dado para um slide específico, crie tensão com lógica irrefutável ou analogia precisa.
- Profundidade não é quantidade de texto — é densidade de informação por linha.
- NUNCA escreva um slide raso que qualquer pessoa poderia escrever sem pesquisa. Cada slide deve conter algo que o leitor não sabia ou não havia conectado antes.
- Exemplo raso: "As redes sociais mudaram o marketing." — qualquer um sabe isso.
- Exemplo profundo: "O alcance orgânico do Facebook caiu 89% em 10 anos. O que era gratuito virou produto." — isso ancora, surpreende, educa.

{dados_section}TREND:
- Título: {trend['titulo']}
- Descrição: {trend['descricao']}
- Tópico: {trend['topico']}

ÂNGULO ESCOLHIDO:
- Título: {angulo['titulo']}
- Formato: {formato}
- Hook: {angulo['hook']}
- Emoção dominante: {angulo['emocao']}
- Perfil alvo: {angulo['perfil_alvo']}

ESTRATÉGIA DE COPY A SEGUIR:
{strategy}

{instruction}

IMPORTANTE sobre prompt_imagem:
- Estilo: cinematic, editorial, futuristic, clean, modern
- Pode incluir personagens famosos do mundo dos negócios/tech se relevante
- Pode incluir logos de empresas conhecidas se relevante
- Sempre em inglês
- Exemplo: "Cinematic editorial photo of Mark Zuckerberg presenting Meta AI, dramatic lighting, futuristic stage, ultra-sharp, professional composition"

{inspiracoes_txt}

Retorne APENAS JSON válido, sem markdown, sem explicações."""
        }]
    )

    try:
        text = response.content[0].text.strip()
        # Remove markdown se vier
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        parsed = json.loads(text)
        # Se Claude retornou lista diretamente, encapsula em dict
        if isinstance(parsed, list):
            return {"slides": parsed}
        return parsed
    except Exception as e:
        print(f"Erro ao parsear copy: {e}")
        print(f"Resposta raw: {response.content[0].text[:300]}")
        return {}


# ─── ENVIAR COPY PRO TELEGRAM ────────────────────────────────────

async def send_copy_to_telegram(copy_data: dict, angulo: dict):
    """Envia a copy COMPLETA pro Telegram para aprovação."""
    bot     = Bot(token=TELEGRAM_TOKEN)
    formato = angulo.get("formato", "carrossel")

    botoes = [
        [
            InlineKeyboardButton("✅ Aprovar e gerar artes", callback_data="copy_approve"),
            InlineKeyboardButton("🔄 Refazer copy", callback_data="copy_redo")
        ]
    ]
    markup = InlineKeyboardMarkup(botoes)

    if formato == "carrossel":
        slides = copy_data.get("slides", [])

        # Cabeçalho
        cabecalho  = f"✍️ *Copy do Carrossel gerada!*\n\n"
        cabecalho += f"📌 *{angulo['titulo']}*\n"
        cabecalho += f"🖼️ {len(slides)} slides\n"
        cabecalho += f"━━━━━━━━━━━━━━━━"

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=cabecalho,
            parse_mode="Markdown"
        )

        # Envia cada slide como mensagem separada
        for slide in slides:
            n      = slide.get("slide", "")
            titulo = slide.get("titulo_bold", "")
            corpo  = slide.get("corpo", "")
            prompt = slide.get("prompt_imagem", "")

            texto  = f"🖼️ *Slide {n}/10*\n"
            texto += f"━━━━━━━━━━━━━━━━\n\n"
            texto += f"*Título:*\n{titulo}\n\n"
            texto += f"*Corpo:*\n{corpo}\n"
            if prompt:
                texto += f"\n_🎨 Imagem: {prompt}_"

            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=texto,
                parse_mode="Markdown"
            )

        # Mensagem final com botões de aprovação
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="━━━━━━━━━━━━━━━━\n\n👇 *Aprovar essa copy ou refazer?*",
            parse_mode="Markdown",
            reply_markup=markup
        )

    else:
        # Reels — envia script completo
        desenvolvimento = copy_data.get("desenvolvimento", [])
        dev_texto = "\n".join([f"• {d}" for d in desenvolvimento])

        texto  = f"✍️ *Script do Reels gerado!*\n\n"
        texto += f"📌 *{angulo['titulo']}*\n"
        texto += f"━━━━━━━━━━━━━━━━\n\n"
        texto += f"🎬 *Hook (0-3s):*\n{copy_data.get('hook', '')}\n\n"
        texto += f"📈 *Desenvolvimento (3-20s):*\n{dev_texto}\n\n"
        texto += f"⚡ *Clímax:*\n{copy_data.get('climax', '')}\n\n"
        texto += f"🔚 *CTA Final:*\n{copy_data.get('cta_final', '')}\n\n"
        texto += f"📱 *Legenda Instagram:*\n{copy_data.get('legenda_instagram', '')}\n\n"
        texto += "━━━━━━━━━━━━━━━━\n\n👇 *Aprovar esse script?*"

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=texto,
            parse_mode="Markdown",
            reply_markup=markup
        )


# ─── HANDLER DE CALLBACKS ────────────────────────────────────────

_copy_approved = False
_redo_copy     = False

async def handle_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _copy_approved, _redo_copy

    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "copy_approve":
        _copy_approved = True
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "✅ *Copy aprovada!*\n\n🎨 Passando pro Designer...\n⏳ Aguarde enquanto as artes são geradas.",
            parse_mode="Markdown"
        )

    elif data == "copy_redo":
        _redo_copy = True
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "🔄 Refazendo a copy...\n⏳ Aguarde um momento.",
            parse_mode="Markdown"
        )


# ─── EXECUTAR AGENTE 3 ───────────────────────────────────────────

async def run_copywriter(final_choice: dict) -> dict:
    """Função principal do Agente 3."""
    global _copy_approved, _redo_copy

    trend  = final_choice.get("trend", {})
    angulo = final_choice.get("angulo_escolhido", {})

    print("✍️  Agente 3 — Copywriter iniciado...")
    print(f"📌 Trend: {trend.get('titulo', '')}")
    print(f"🎯 Ângulo: {angulo.get('titulo', '')}")
    print(f"📐 Formato: {angulo.get('formato', '')}")

    copy_data = None
    attempts  = 0

    while True:
        attempts += 1
        _copy_approved = False
        _redo_copy     = False

        # 1. Gera copy com Claude
        print(f"\n⏳ Gerando copy (tentativa {attempts})...")
        copy_data = generate_copy_with_claude(trend, angulo)
        print("✅ Copy gerada!")

        # 2. Envia pro Telegram
        await send_copy_to_telegram(copy_data, angulo)
        print("📲 Copy enviada pro Telegram. Aguardando aprovação...")

        # 3. Inicia bot pra escutar resposta
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CallbackQueryHandler(handle_copy_callback))

        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        # Aguarda decisão
        while not _copy_approved and not _redo_copy:
            await asyncio.sleep(2)

        await app.updater.stop()
        await app.stop()
        await app.shutdown()

        if _copy_approved:
            break
        else:
            print("🔄 Refazendo copy...")

    # Salva resultado final
    final_output = {
        "trend": trend,
        "angulo": angulo,
        "copy": copy_data,
        "formato": angulo.get("formato", "carrossel")
    }

    with open("/tmp/copy_result.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Copy aprovada após {attempts} tentativa(s)!")
    return final_output


if __name__ == "__main__":
    try:
        with open("/tmp/final_choice.json", "r", encoding="utf-8") as f:
            final_choice = json.load(f)
    except FileNotFoundError:
        print("❌ Rode o agent2_strategist.py primeiro.")
        exit(1)

    result = asyncio.run(run_copywriter(final_choice))
    print(f"\n✅ Copy do {result['formato']} pronta!")
