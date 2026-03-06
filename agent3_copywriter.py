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

ESTRUTURA DOS 10 SLIDES:

Slide 1 — COVER (Hook + Interrupção)
- Afirmação polêmica, contraintuitiva ou revelação chocante
- NÃO usa pergunta — usa afirmação direta com tensão
- Cria "dívida mental": o leitor PRECISA deslizar pra fechar a história
- Exemplos de motores: Ameaça ("Quem não entender isso..."), Revelação ("X é Y — e ninguém sabe"), Quebra de percepção ("X não é Y... é Z")

Slide 2 — PROBLEMA (Espelho)
- Mostra o que "todo mundo acredita" e cria identificação imediata
- Leitor pensa: "sou eu"
- Contextualização rápida: "Durante décadas..." / "Tudo começou quando..."

Slide 3 — CONTRASTE (Fricção)
- Aponta o erro da visão comum e cria fricção
- Quebra o "piloto automático" da crença antiga
- Estrutura "certo... ERRADO" disfarçada

Slide 4 — DIAGNÓSTICO (Culpado Oculto)
- Explica o que está por trás do problema
- Revela o "culpado oculto" — algo que a pessoa não havia considerado
- Leitor sente: "agora faz sentido"

Slide 5 — O VILÃO (Inimigo Comum)
- Nomeia o obstáculo (algoritmo, crença, método, sistema)
- Externaliza parte da culpa (alívio emocional)
- Direciona raiva/frustração pra algo claro

Slide 6 — REFRAME (Novo Jogo)
- Traz a nova visão e reposiciona a mentalidade
- Não dá "dicas" — dá um novo sistema de interpretação
- "O jogo real é..." / "A lição não é sobre X... é sobre Y"

Slide 7 — A LIÇÃO (Consequência)
- Mostra o que muda quando a nova visão é adotada
- Amplifica desejo do ganho E medo da perda simultaneamente

Slide 8 — PROVA (Sem imagem — só texto)
- Solidifica a crença nova com dados, casos reais ou lógica irrefutável
- Reduz ceticismo — sem isso vira só opinião bem escrita

Slide 9 — PROVOCAÇÃO (Penúltimo — fundo escuro)
- Crescimento real não vem de empurrões — vem de estrutura
- Deixa o leitor com desconforto, autoavaliação, vontade de comentar

Slide 10 — CTA (Final — fundo preto com foto)
- Pergunta direta que obriga escolha
- NÃO termina com "e aí, gostou?"
- Modelo: "Você vai continuar fazendo X? Ou vai Y?"
- Inclui instrução: "Comente '[palavra]' e eu te mando..."

REGRAS DE MICROCOPY:
- Frases curtas. Pausas visuais. Ritmo.
- Máximo 3 linhas por bloco de texto
- Nunca parágrafos longos
- Tom editorial — não de coach
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

def generate_copy_with_claude(trend: dict, angulo: dict) -> dict:
    """Gera a copy completa seguindo a estratégia da Wavy."""

    formato = angulo.get("formato", "carrossel")
    strategy = COPY_STRATEGY_CAROUSEL if formato == "carrossel" else COPY_STRATEGY_REELS

    if formato == "carrossel":
        instruction = """
Escreva a copy completa dos 10 slides do carrossel.
Para cada slide retorne:
- "slide": número do slide (1-10)
- "titulo_bold": texto em negrito (título principal do slide) — máximo 10 palavras
- "corpo": texto do corpo — máximo 3 linhas curtas
- "prompt_imagem": descrição em inglês para gerar imagem cinematográfica no Freepik (slides 1-7 e 10 têm imagem)

Slides sem imagem: slide 8 (só texto) e slide 9 (fundo escuro, só texto).
Slide 10: é o CTA final — inclui uma "palavra_cta" para o comentário (ex: "framework", "método", "guia").
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

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": f"""Você é o Copywriter da Wavy — agência de marketing digital.
Seu estilo é editorial, tenso, cinematográfico. Nunca de coach motivacional.
Tom: direto, inteligente, provoca reflexão. Público: empreendedores e gestores de marketing digital brasileiros.

TREND:
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
