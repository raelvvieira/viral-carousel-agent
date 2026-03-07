“””
SCHEDULER — WAVY AGENTS
Conecta os 4 agentes e agenda execução automática
3x por semana (segunda, quarta e sexta às 8h).
Também aceita comandos manuais via Telegram.
“””

import os
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Importa os agentes

from agent1_scout import run_scout
from agent2_strategist import run_strategist
from agent3_copywriter import run_copywriter
from agent4_designer import run_designer

# ─── CONFIGURAÇÕES ───────────────────────────────────────────────

TELEGRAM_TOKEN   = os.getenv(“TELEGRAM_TOKEN”)
TELEGRAM_CHAT_ID = int(os.getenv(“TELEGRAM_CHAT_ID”))

# ─── LOGS ────────────────────────────────────────────────────────

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s [%(levelname)s] %(message)s”,
datefmt=”%d/%m/%Y %H:%M:%S”
)
log = logging.getLogger(“wavy-scheduler”)

# Controle de estado global

_pipeline_running = False

# Guarda os títulos já mostrados na sessão atual (acumula a cada “buscar outros”)

_shown_trend_titles: list[str] = []

# Guarda o resultado atual do Scout para o Agente 2 usar

_current_trends_data: dict = {}

# ─── ENVIAR TRENDS COM BOTÕES ────────────────────────────────────

async def send_trends_to_telegram(bot: Bot, trends_data: dict):
“””
Envia as 5 trends pro Telegram com botões numerados para escolha
e botão para buscar outros temas.
“””
global _current_trends_data
_current_trends_data = trends_data

```
trends = trends_data.get("trends", [])
if not trends:
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="⚠️ Nenhuma trend encontrada. Tente novamente."
    )
    return

# Monta mensagem com as 5 trends
texto = "📊 *Top 5 trends de hoje:*\n\n"
emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
for i, trend in enumerate(trends):
    texto += (
        f"{emojis[i]} *{trend['titulo']}*\n"
        f"📌 {trend['topico']} • 🔥 {trend['score_viralidade']}/100\n"
        f"_{trend['descricao']}_\n\n"
    )

# Botões numéricos para escolher a trend
botoes_escolha = [
    InlineKeyboardButton(emojis[i], callback_data=f"trend_{i}")
    for i in range(len(trends))
]

# Botão para buscar outros temas (linha separada)
botao_outros = InlineKeyboardButton("🔄 Buscar outros temas", callback_data="scout_retry")

keyboard = InlineKeyboardMarkup([
    botoes_escolha,
    [botao_outros]
])

await bot.send_message(
    chat_id=TELEGRAM_CHAT_ID,
    text=texto,
    parse_mode="Markdown",
    reply_markup=keyboard
)
```

# ─── PIPELINE COMPLETO ───────────────────────────────────────────

async def run_full_pipeline(retry: bool = False):
“””
Executa o pipeline completo dos 4 agentes em sequência.
Se retry=True, o Agente 2 em diante já foi iniciado pelo callback —
este método só roda o Scout e envia os temas.
“””
global _pipeline_running, _shown_trend_titles

```
if _pipeline_running:
    log.warning("Pipeline já está rodando, ignorando nova chamada.")
    return

_pipeline_running = True
bot = Bot(token=TELEGRAM_TOKEN)
now = datetime.now().strftime("%d/%m/%Y às %H:%M")

log.info("🚀 Pipeline iniciado")

try:
    if not retry:
        # Primeira execução: reseta os temas vistos
        _shown_trend_titles = []
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"🚀 *Wavy Content Bot iniciado!*\n📅 {now}\n\n⏳ Buscando tendências...",
            parse_mode="Markdown"
        )

    # ── AGENTE 1 — Scout ──
    log.info("Agente 1 — Scout")
    trends_data = await run_scout(excluded_titles=_shown_trend_titles if _shown_trend_titles else None)

    if not trends_data.get("trends"):
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="⚠️ Nenhuma trend encontrada hoje. Tente novamente mais tarde."
        )
        return

    # Acumula os títulos mostrados para evitar repetição em futuras buscas
    for trend in trends_data.get("trends", []):
        titulo = trend.get("titulo", "")
        if titulo and titulo not in _shown_trend_titles:
            _shown_trend_titles.append(titulo)

    # Envia as trends com botões (escolha + buscar outros)
    await send_trends_to_telegram(bot, trends_data)

    # Agente 2 em diante só roda quando o usuário escolher uma trend
    # (via callback_query handler)

except Exception as e:
    log.error(f"❌ Erro no pipeline: {e}")
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"❌ *Erro no pipeline*\n\n`{str(e)[:200]}`\n\nVerifique os logs no Railway.",
        parse_mode="Markdown"
    )
finally:
    _pipeline_running = False
```

async def run_pipeline_from_trend(trend_index: int):
“”“Continua o pipeline a partir da trend escolhida (Agentes 2, 3 e 4).”””
global _pipeline_running, _current_trends_data

```
_pipeline_running = True
bot = Bot(token=TELEGRAM_TOKEN)

try:
    # ── AGENTE 2 — Estrategista ──
    log.info("Agente 2 — Estrategista")
    final_choice = await run_strategist(_current_trends_data, selected_index=trend_index)
    if not final_choice:
        return

    # ── AGENTE 3 — Copywriter ──
    log.info("Agente 3 — Copywriter")
    copy_result = await run_copywriter(final_choice)
    if not copy_result:
        return

    # ── AGENTE 4 — Designer ──
    log.info("Agente 4 — Designer")
    drive_links = await run_designer(copy_result)

    log.info(f"✅ Pipeline concluído! {len(drive_links)} slides gerados.")

except Exception as e:
    log.error(f"❌ Erro no pipeline (trend): {e}")
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"❌ *Erro ao continuar pipeline*\n\n`{str(e)[:200]}`",
        parse_mode="Markdown"
    )
finally:
    _pipeline_running = False
```

# ─── CALLBACK: BOTÕES INLINE ─────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
“”“Trata cliques nos botões inline (escolha de trend ou buscar outros).”””
query = update.callback_query
await query.answer()

```
if query.message.chat.id != TELEGRAM_CHAT_ID:
    return

data = query.data

# ── Botão: buscar outros temas ──
if data == "scout_retry":
    global _pipeline_running
    # Reseta o flag caso tenha ficado travado
    _pipeline_running = False

    await query.message.reply_text(
        "🔄 *Buscando outros temas...*\n\n"
        "⏳ Aguarde, estou procurando tendências diferentes!",
        parse_mode="Markdown"
    )
    asyncio.create_task(run_full_pipeline(retry=True))
    return

# ── Botão: escolha de trend (trend_0 a trend_4) ──
if data.startswith("trend_"):
    if _pipeline_running:
        await query.message.reply_text("⚠️ Aguarde, o sistema ainda está processando.")
        return

    index = int(data.split("_")[1])
    trends = _current_trends_data.get("trends", [])

    if index >= len(trends):
        await query.message.reply_text("❌ Trend não encontrada.")
        return

    trend = trends[index]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    await query.message.reply_text(
        f"✅ *Trend selecionada:*\n\n"
        f"{emojis[index]} *{trend['titulo']}*\n\n"
        f"⏳ Gerando ângulos e copy...",
        parse_mode="Markdown"
    )

    asyncio.create_task(run_pipeline_from_trend(index))
```

# ─── COMANDOS DO TELEGRAM ────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_chat.id != TELEGRAM_CHAT_ID:
return

```
scheduler = context.bot_data.get("scheduler")
job = scheduler.get_job("wavy_pipeline") if scheduler else None
proxima = job.next_run_time.strftime("%d/%m/%Y às %H:%M") if job else "—"

await update.message.reply_text(
    f"👋 *Wavy Content Bot*\n\n"
    f"Comandos disponíveis:\n\n"
    f"▶️ /rodar — Executa o pipeline agora\n"
    f"📊 /status — Ver status do sistema\n"
    f"❓ /ajuda — Ver todos os comandos\n\n"
    f"📅 Próxima execução automática:\n*{proxima}*",
    parse_mode="Markdown"
)
```

async def cmd_rodar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_chat.id != TELEGRAM_CHAT_ID:
return

```
if _pipeline_running:
    await update.message.reply_text("⚠️ O pipeline já está rodando! Aguarde terminar.")
    return

await update.message.reply_text(
    "▶️ *Iniciando pipeline manualmente...*\n\n"
    "Você receberá as atualizações aqui mesmo!",
    parse_mode="Markdown"
)

asyncio.create_task(run_full_pipeline())
```

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_chat.id != TELEGRAM_CHAT_ID:
return

```
scheduler = context.bot_data.get("scheduler")
job = scheduler.get_job("wavy_pipeline") if scheduler else None
proxima = job.next_run_time.strftime("%d/%m/%Y às %H:%M") if job else "—"
status_pipeline = "🔄 Rodando agora" if _pipeline_running else "✅ Aguardando"
temas_vistos = len(_shown_trend_titles)

await update.message.reply_text(
    f"📊 *Status do Sistema*\n\n"
    f"🤖 Bot: Online\n"
    f"⚙️ Pipeline: {status_pipeline}\n"
    f"📅 Próxima execução: *{proxima}*\n"
    f"🗓️ Agenda: Seg, Qua e Sex às 8h\n"
    f"🔄 Temas vistos nesta sessão: *{temas_vistos}*",
    parse_mode="Markdown"
)
```

async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_chat.id != TELEGRAM_CHAT_ID:
return

```
await update.message.reply_text(
    "❓ *Comandos disponíveis*\n\n"
    "▶️ /rodar — Executa o pipeline agora\n"
    "📊 /status — Status do sistema\n"
    "🔁 /start — Mensagem de boas-vindas\n"
    "❓ /ajuda — Esta mensagem\n\n"
    "_O pipeline roda automaticamente\nseg, qua e sex às 8h._",
    parse_mode="Markdown"
)
```

# ─── SCHEDULER ───────────────────────────────────────────────────

async def main():
scheduler = AsyncIOScheduler(timezone=“America/Sao_Paulo”)
scheduler.add_job(
run_full_pipeline,
trigger=CronTrigger(
day_of_week=“mon,wed,fri”,
hour=8,
minute=0,
timezone=“America/Sao_Paulo”
),
id=“wavy_pipeline”,
name=“Wavy Content Pipeline”,
replace_existing=True
)
scheduler.start()

```
app = Application.builder().token(TELEGRAM_TOKEN).build()
app.bot_data["scheduler"] = scheduler

# Comandos
app.add_handler(CommandHandler("start",  cmd_start))
app.add_handler(CommandHandler("rodar",  cmd_rodar))
app.add_handler(CommandHandler("status", cmd_status))
app.add_handler(CommandHandler("ajuda",  cmd_ajuda))

# Callbacks dos botões inline
app.add_handler(CallbackQueryHandler(handle_callback))

await app.bot.set_my_commands([
    BotCommand("rodar",  "Executar pipeline agora"),
    BotCommand("status", "Ver status do sistema"),
    BotCommand("ajuda",  "Ver todos os comandos"),
])

await app.initialize()
await app.start()
await app.updater.start_polling()

job     = scheduler.get_job("wavy_pipeline")
proxima = job.next_run_time.strftime("%d/%m/%Y às %H:%M")
log.info(f"✅ Sistema online — próxima execução: {proxima}")

await app.bot.send_message(
    chat_id=TELEGRAM_CHAT_ID,
    text=(
        f"✅ *Wavy Content Bot online!*\n\n"
        f"🤖 Sistema iniciado com sucesso\n"
        f"📅 Próxima execução: *{proxima}*\n\n"
        f"▶️ Para rodar agora: /rodar\n"
        f"📊 Para ver status: /status\n\n"
        f"_Rodando automaticamente seg, qua e sex às 8h_"
    ),
    parse_mode="Markdown"
)

while True:
    await asyncio.sleep(60)
```

if **name** == “**main**”:
asyncio.run(main())