"""
SCHEDULER — WAVY AGENTS
Conecta os 4 agentes e agenda execução automática
3x por semana (segunda, quarta e sexta às 8h).
Também aceita comandos manuais via Telegram.
"""

import os
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

# Importa os agentes
from agent1_scout import run_scout
from agent2_strategist import run_strategist
from agent3_copywriter import run_copywriter
from agent4_designer import run_designer

# ─── CONFIGURAÇÕES ───────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

# ─── LOGS ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)
log = logging.getLogger("wavy-scheduler")

# Controle para evitar execuções paralelas
_pipeline_running = False


# ─── PIPELINE COMPLETO ───────────────────────────────────────────

async def run_full_pipeline():
    """Executa o pipeline completo dos 4 agentes em sequência."""
    global _pipeline_running

    if _pipeline_running:
        log.warning("Pipeline já está rodando, ignorando nova chamada.")
        return

    _pipeline_running = True
    bot = Bot(token=TELEGRAM_TOKEN)
    now = datetime.now().strftime("%d/%m/%Y às %H:%M")

    log.info("🚀 Pipeline iniciado")

    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"🚀 *Wavy Content Bot iniciado!*\n📅 {now}\n\n⏳ Buscando tendências...",
            parse_mode="Markdown"
        )

        # ── AGENTE 1 — Scout ──
        log.info("Agente 1 — Scout")
        trends_data = await run_scout()

        if not trends_data.get("trends"):
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text="⚠️ Nenhuma trend encontrada hoje. Tente novamente mais tarde.",
                parse_mode="Markdown"
            )
            return

        # ── AGENTE 2 — Estrategista ──
        log.info("Agente 2 — Estrategista")
        final_choice = await run_strategist(trends_data)
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

        log.info(f"✅ Pipeline concluído! {len(drive_links)} slides no Drive.")

    except Exception as e:
        log.error(f"❌ Erro no pipeline: {e}")
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"❌ *Erro no pipeline*\n\n`{str(e)[:200]}`\n\nVerifique os logs no Railway.",
            parse_mode="Markdown"
        )
    finally:
        _pipeline_running = False


# ─── COMANDOS DO TELEGRAM ────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao /start com lista de comandos."""
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return

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


async def cmd_rodar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executa o pipeline manualmente via /rodar."""
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return

    if _pipeline_running:
        await update.message.reply_text(
            "⚠️ O pipeline já está rodando! Aguarde terminar."
        )
        return

    await update.message.reply_text(
        "▶️ *Iniciando pipeline manualmente...*\n\n"
        "Você receberá as atualizações aqui mesmo!",
        parse_mode="Markdown"
    )

    # Roda em background para não bloquear o bot
    asyncio.create_task(run_full_pipeline())


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra status atual do sistema."""
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return

    scheduler = context.bot_data.get("scheduler")
    job = scheduler.get_job("wavy_pipeline") if scheduler else None
    proxima = job.next_run_time.strftime("%d/%m/%Y às %H:%M") if job else "—"
    status_pipeline = "🔄 Rodando agora" if _pipeline_running else "✅ Aguardando"

    await update.message.reply_text(
        f"📊 *Status do Sistema*\n\n"
        f"🤖 Bot: Online\n"
        f"⚙️ Pipeline: {status_pipeline}\n"
        f"📅 Próxima execução: *{proxima}*\n"
        f"🗓️ Agenda: Seg, Qua e Sex às 8h",
        parse_mode="Markdown"
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todos os comandos disponíveis."""
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return

    await update.message.reply_text(
        "❓ *Comandos disponíveis*\n\n"
        "▶️ /rodar — Executa o pipeline agora\n"
        "📊 /status — Status do sistema\n"
        "🔁 /start — Mensagem de boas-vindas\n"
        "❓ /ajuda — Esta mensagem\n\n"
        "_O pipeline roda automaticamente\nseg, qua e sex às 8h._",
        parse_mode="Markdown"
    )


# ─── SCHEDULER ───────────────────────────────────────────────────

async def main():
    """Inicia o scheduler e o bot Telegram."""

    # Configura o scheduler
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_full_pipeline,
        trigger=CronTrigger(
            day_of_week="mon,wed,fri",
            hour=8,
            minute=0,
            timezone="America/Sao_Paulo"
        ),
        id="wavy_pipeline",
        name="Wavy Content Pipeline",
        replace_existing=True
    )
    scheduler.start()

    # Configura o bot
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.bot_data["scheduler"] = scheduler

    # Registra comandos
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("rodar",  cmd_rodar))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ajuda",  cmd_ajuda))

    # Define menu de comandos no Telegram
    await app.bot.set_my_commands([
        BotCommand("rodar",  "Executar pipeline agora"),
        BotCommand("status", "Ver status do sistema"),
        BotCommand("ajuda",  "Ver todos os comandos"),
    ])

    # Inicia o bot
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Notifica que está online
    job    = scheduler.get_job("wavy_pipeline")
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

    # Mantém processo vivo
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
