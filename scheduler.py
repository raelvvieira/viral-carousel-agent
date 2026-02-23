"""
SCHEDULER — WAVY AGENTS
Conecta os 4 agentes e agenda execução automática
3x por semana (segunda, quarta e sexta às 8h).
"""

import os
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

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


# ─── PIPELINE COMPLETO ───────────────────────────────────────────

async def run_full_pipeline():
    """Executa o pipeline completo dos 4 agentes em sequência."""
    
    bot  = Bot(token=TELEGRAM_TOKEN)
    now  = datetime.now().strftime("%d/%m/%Y às %H:%M")

    log.info("🚀 Pipeline iniciado")

    try:
        # Avisa que começou
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
                text="⚠️ Nenhuma trend encontrada hoje. Tentaremos novamente na próxima execução.",
                parse_mode="Markdown"
            )
            return

        # ── AGENTE 2 — Estrategista ──
        log.info("Agente 2 — Estrategista")
        final_choice = await run_strategist(trends_data)

        if not final_choice:
            log.warning("Nenhuma escolha feita no Estrategista")
            return

        # ── AGENTE 3 — Copywriter ──
        log.info("Agente 3 — Copywriter")
        copy_result = await run_copywriter(final_choice)

        if not copy_result:
            log.warning("Copy não gerada")
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


# ─── SCHEDULER ───────────────────────────────────────────────────

async def main():
    """Inicia o scheduler e mantém o processo rodando."""

    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")

    # Roda segunda, quarta e sexta às 8h (horário de Florianópolis)
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
    log.info("✅ Scheduler iniciado — rodando seg/qua/sex às 8h (Florianópolis)")
    log.info("⏳ Aguardando próxima execução...")

    # Mostra próxima execução
    job  = scheduler.get_job("wavy_pipeline")
    next = job.next_run_time
    log.info(f"📅 Próxima execução: {next.strftime('%d/%m/%Y às %H:%M')}")

    # Notifica no Telegram que o sistema está online
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            f"✅ *Wavy Content Bot online!*\n\n"
            f"🤖 Sistema iniciado com sucesso\n"
            f"📅 Próxima execução: *{next.strftime('%d/%m/%Y às %H:%M')}*\n\n"
            f"_Rodando automaticamente seg, qua e sex às 8h_"
        ),
        parse_mode="Markdown"
    )

    # Mantém processo vivo
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
