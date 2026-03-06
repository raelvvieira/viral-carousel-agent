"""
AGENTE 2 — ESTRATEGISTA
Recebe as trends do Agente 1, envia pro Telegram com botões de escolha,
aguarda aprovação e sugere 3 ângulos de conteúdo com formato.
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


# ─── ENVIAR TRENDS PRO TELEGRAM ──────────────────────────────────

async def send_trends_to_telegram(trends_data: dict) -> str:
    """
    Manda as 5 trends pro Telegram com botões inline.
    Retorna o message_id pra rastrear a resposta.
    """
    bot = Bot(token=TELEGRAM_TOKEN)
    trends = trends_data.get("trends", [])
    data   = trends_data.get("data_coleta", "")

    # Monta o texto da mensagem
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    texto  = f"🔥 *Wavy Content Bot*\n"
    texto += f"📅 Trends de {data}\n\n"
    texto += "Aqui estão as tendências identificadas hoje:\n\n"

    for i, trend in enumerate(trends[:5]):
        score = trend.get("score_viralidade", 0)
        emoji_score = "🔴" if score >= 80 else "🟡" if score >= 60 else "🟢"
        texto += f"{emojis[i]} *{trend['titulo']}*\n"
        texto += f"   {emoji_score} Score: {score}/100 | 📌 {trend['topico']}\n"
        texto += f"   _{trend['descricao'][:100]}..._\n\n"

    texto += "👇 *Qual trend quer explorar hoje?*"

    # Monta os botões
    botoes = []
    for i, trend in enumerate(trends[:5]):
        botoes.append([InlineKeyboardButton(
            f"{emojis[i]} {trend['titulo'][:40]}",
            callback_data=f"trend_{i}"
        )])

    markup = InlineKeyboardMarkup(botoes)

    msg = await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=texto,
        parse_mode="Markdown",
        reply_markup=markup
    )
    return str(msg.message_id)


# ─── GERAR ÂNGULOS COM CLAUDE ────────────────────────────────────

def generate_angles_with_claude(trend: dict) -> dict:
    """
    Recebe a trend escolhida e gera 3 ângulos de conteúdo
    com formato sugerido (carrossel ou reels).
    """
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Você é um estrategista de conteúdo viral para Instagram especializado em Marketing Digital, Meta Ads, Google Ads, IA e Negócios.

Trend identificada:
- Título: {trend['titulo']}
- Descrição: {trend['descricao']}
- Tópico: {trend['topico']}
- Score de viralidade: {trend['score_viralidade']}/100

Sua tarefa: gerar 3 ângulos de conteúdo viral diferentes para essa trend.

Para cada ângulo considere:
- O formato é sempre carrossel de 10 slides
- Qual é o hook principal (o que vai parar o scroll)
- Qual emoção dominante (indignação, surpresa, identificação, medo, admiração)
- Para qual perfil de seguidor é mais relevante

IMPORTANTE: O formato deve ser SEMPRE "carrossel" — nunca "reels".

Retorne APENAS um JSON válido neste formato:
{{
  "trend_titulo": "{trend['titulo']}",
  "angulos": [
    {{
      "numero": 1,
      "titulo": "Título do ângulo em português",
      "formato": "carrossel",
      "hook": "Frase de abertura impactante que vai no slide 1 ou início do reels",
      "emocao": "identificação",
      "descricao": "2-3 frases explicando a abordagem e por que vai viralizar",
      "perfil_alvo": "Empreendedores que gastam em tráfego"
    }},
    {{
      "numero": 2,
      "titulo": "Título do ângulo 2",
      "formato": "carrossel",
      "hook": "Hook do carrossel",
      "emocao": "surpresa",
      "descricao": "Descrição do ângulo 2",
      "perfil_alvo": "Gestores de tráfego"
    }},
    {{
      "numero": 3,
      "titulo": "Título do ângulo 3",
      "formato": "carrossel",
      "hook": "Hook do carrossel",
      "emocao": "indignação",
      "descricao": "Descrição do ângulo 3",
      "perfil_alvo": "Donos de negócio digital"
    }}
  ]
}}"""
        }]
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"Erro ao parsear ângulos: {e}")
        return {"angulos": []}


# ─── ENVIAR ÂNGULOS PRO TELEGRAM ─────────────────────────────────

async def send_angles_to_telegram(angles_data: dict):
    """Envia os 3 ângulos gerados pro Telegram com botões de escolha."""
    bot    = Bot(token=TELEGRAM_TOKEN)
    angulos = angles_data.get("angulos", [])
    emojis  = ["1️⃣", "2️⃣", "3️⃣"]
    formato_emoji = {"carrossel": "🖼️", "reels": "🎬"}

    texto  = f"✅ *Trend selecionada!*\n"
    texto += f"📌 *{angles_data.get('trend_titulo', '')}*\n\n"
    texto += "Aqui estão os 3 ângulos sugeridos:\n\n"

    for i, angulo in enumerate(angulos[:3]):
        fmt   = angulo.get("formato", "carrossel")
        emoji = formato_emoji.get(fmt, "🖼️")
        texto += f"{emojis[i]} *{angulo['titulo']}*\n"
        texto += f"   {emoji} Formato: {fmt.capitalize()}\n"
        texto += f"   💡 Hook: _{angulo['hook'][:80]}_\n"
        texto += f"   ❤️ Emoção: {angulo['emocao'].capitalize()}\n"
        texto += f"   👤 Para: {angulo['perfil_alvo']}\n\n"

    texto += "👇 *Qual ângulo quer desenvolver?*"

    botoes = []
    for i, angulo in enumerate(angulos[:3]):
        fmt   = angulo.get("formato", "carrossel")
        emoji = formato_emoji.get(fmt, "🖼️")
        botoes.append([InlineKeyboardButton(
            f"{emojis[i]} {emoji} {angulo['titulo'][:35]}",
            callback_data=f"angulo_{i}"
        )])

    markup = InlineKeyboardMarkup(botoes)

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=texto,
        parse_mode="Markdown",
        reply_markup=markup
    )


# ─── HANDLER DE CALLBACKS ────────────────────────────────────────

# Variáveis globais pra guardar estado entre callbacks
_trends_data   = {}
_angles_data   = {}
_chosen_trend  = None
_chosen_angle  = None


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa os cliques nos botões do Telegram."""
    global _chosen_trend, _chosen_angle, _angles_data

    query = update.callback_query
    await query.answer()
    data  = query.data

    # ── Usuário escolheu uma trend ──
    if data.startswith("trend_"):
        idx          = int(data.split("_")[1])
        _chosen_trend = _trends_data.get("trends", [])[idx]

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ Trend escolhida: *{_chosen_trend['titulo']}*\n\n⏳ Gerando ângulos...",
            parse_mode="Markdown"
        )

        # Gera ângulos com Claude
        _angles_data = generate_angles_with_claude(_chosen_trend)

        # Salva pra o Agente 3 usar
        with open("/tmp/angles_result.json", "w", encoding="utf-8") as f:
            json.dump({
                "trend": _chosen_trend,
                "angulos": _angles_data
            }, f, ensure_ascii=False, indent=2)

        # Envia ângulos pro Telegram
        await send_angles_to_telegram(_angles_data)

    # ── Usuário escolheu um ângulo ──
    elif data.startswith("angulo_"):
        idx           = int(data.split("_")[1])
        _chosen_angle = _angles_data.get("angulos", [])[idx]

        await query.edit_message_reply_markup(reply_markup=None)

        formato = _chosen_angle.get("formato", "carrossel")
        emoji   = "🖼️" if formato == "carrossel" else "🎬"

        await query.message.reply_text(
            f"✅ Ângulo aprovado!\n\n"
            f"{emoji} *{_chosen_angle['titulo']}*\n"
            f"📌 Formato: {formato.capitalize()}\n\n"
            f"⏳ Passando pro Copywriter...",
            parse_mode="Markdown"
        )

        # Salva escolha final pra o Agente 3
        final_choice = {
            "trend": _chosen_trend,
            "angulo_escolhido": _chosen_angle
        }
        with open("/tmp/final_choice.json", "w", encoding="utf-8") as f:
            json.dump(final_choice, f, ensure_ascii=False, indent=2)

        print(f"✅ Escolha final salva: {_chosen_angle['titulo']}")


# ─── EXECUTAR AGENTE 2 ───────────────────────────────────────────

async def run_strategist(trends_data: dict):
    """Função principal do Agente 2."""
    global _trends_data
    _trends_data = trends_data

    print("🧠 Agente 2 — Estrategista iniciado...")

    # 1. Envia trends pro Telegram
    print("📲 Enviando trends pro Telegram...")
    await send_trends_to_telegram(trends_data)
    print("✅ Trends enviadas! Aguardando sua escolha no Telegram...")

    # 2. Inicia o bot pra escutar os callbacks
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 Bot ouvindo seus cliques...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Aguarda até que a escolha final seja feita
    while not os.path.exists("/tmp/final_choice.json"):
        await asyncio.sleep(2)

    await app.updater.stop()
    await app.stop()
    await app.shutdown()

    # Retorna a escolha final
    with open("/tmp/final_choice.json", "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    # Teste standalone — carrega resultado do Agente 1
    try:
        with open("/tmp/trends_result.json", "r", encoding="utf-8") as f:
            trends = json.load(f)
    except FileNotFoundError:
        print("❌ Rode o agent1_scout.py primeiro para gerar trends_result.json")
        exit(1)

    result = asyncio.run(run_strategist(trends))
    print(f"\n✅ Escolha final: {result['angulo_escolhido']['titulo']}")
