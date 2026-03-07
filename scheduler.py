"""
SCHEDULER - WAVY AGENTS
"""

import os
import asyncio
import logging
import traceback
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from agent1_scout import run_scout
from agent2_strategist import run_strategist
from agent3_copywriter import run_copywriter
from agent4_designer import run_designer

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
log = logging.getLogger("wavy-scheduler")

_pipeline_running = False
_shown_trend_titles = []
_current_trends_data = {}


async def notify(bot, text, parse_mode="Markdown"):
    log.info(text.replace("*","").replace("_",""))
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode=parse_mode)
    except Exception as e:
        log.error(f"Erro Telegram: {e}")


async def send_trends_to_telegram(bot, trends_data):
    global _current_trends_data
    _current_trends_data = trends_data
    trends = trends_data.get("trends", [])
    if not trends:
        await notify(bot, "Nenhuma trend encontrada. Tente novamente.")
        return
    emojis = ["1", "2", "3", "4", "5"]
    texto = "Top 5 trends de hoje:\n\n"
    for i, trend in enumerate(trends):
        texto += f"{emojis[i]}. *{trend['titulo']}*\n{trend['topico']} - {trend['score_viralidade']}/100\n_{trend['descricao']}_\n\n"
    texto += "Escolha um tema ou busque outros:"
    botoes = [InlineKeyboardButton(f"{emojis[i]}", callback_data=f"trend_{i}") for i in range(len(trends))]
    keyboard = InlineKeyboardMarkup([botoes, [InlineKeyboardButton("Buscar outros temas", callback_data="scout_retry")]])
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=texto, parse_mode="Markdown", reply_markup=keyboard)


async def run_scout_step(bot, retry=False):
    global _pipeline_running, _shown_trend_titles
    _pipeline_running = True
    now = datetime.now().strftime("%d/%m/%Y as %H:%M")
    try:
        if not retry:
            _shown_trend_titles = []
            await notify(bot, f"Wavy Content Bot iniciado!\n{now}\n\nAgente 1 - Scout\nConectando nas fontes RSS e Reddit...")
        else:
            await notify(bot, f"Buscando outros temas...\n\nAgente 1 - Scout\nProcurando tendencias diferentes das {len(_shown_trend_titles)} ja mostradas...")

        trends_data = await run_scout(excluded_titles=_shown_trend_titles if _shown_trend_titles else None)

        if not trends_data.get("trends"):
            await notify(bot, "Nenhuma trend encontrada hoje. Tente novamente mais tarde.")
            return

        count = len(trends_data.get("trends", []))
        await notify(bot, f"Scout concluido!\n{count} tendencias encontradas\n\nPreparando lista...")

        for trend in trends_data.get("trends", []):
            titulo = trend.get("titulo", "")
            if titulo and titulo not in _shown_trend_titles:
                _shown_trend_titles.append(titulo)

        await send_trends_to_telegram(bot, trends_data)

    except Exception as e:
        err = traceback.format_exc()
        log.error(f"Erro Scout: {err}")
        await notify(bot, f"Erro no Agente 1 - Scout\n\n{str(e)[:300]}\n\nVerifique os logs no Railway.")
    finally:
        _pipeline_running = False


async def run_pipeline_from_trend(trend_index):
    global _pipeline_running, _current_trends_data
    _pipeline_running = True
    bot = Bot(token=TELEGRAM_TOKEN)
    trends = _current_trends_data.get("trends", [])

    if trend_index >= len(trends):
        await notify(bot, "Trend nao encontrada. Rode /rodar novamente.")
        _pipeline_running = False
        return

    trend = trends[trend_index]

    try:
        await notify(bot, f"Agente 2 - Estrategista\n\nTema escolhido: {trend['titulo']}\n\nGerando 3 angulos para o carrossel...")

        final_choice = await run_strategist(_current_trends_data, selected_index=trend_index)

        if not final_choice:
            await notify(bot, "Estrategista falhou. Tente selecionar outro tema.")
            return

        angulo_titulo = final_choice.get("angulo", {}).get("titulo", "")
        await notify(bot, f"Estrategista concluido!\n\nAngulo selecionado:\n{angulo_titulo}\n\nPassando para o Copywriter...")

        await notify(bot, "Agente 3 - Copywriter\n\nPesquisando dados sobre o tema...\nGerando copy para os 10 slides...\n\n(Isso pode levar 1-2 minutos)")

        copy_result = await run_copywriter(final_choice)

        if not copy_result:
            await notify(bot, "Copywriter falhou. Verifique os logs no Railway.")
            return

        slides_count = len(copy_result.get("copy", {}).get("slides", []))
        await notify(bot, f"Copywriter concluido!\n{slides_count} slides escritos\n\nPassando para o Designer...")

        await notify(bot, "Agente 4 - Designer\n\nGerando imagens no Freepik...\nRenderizando slides em PNG...\n\n(Isso pode levar 3-5 minutos)")

        png_paths = await run_designer(copy_result)

        await notify(bot, f"Pipeline concluido com sucesso!\n\n{len(png_paths)} slides gerados\nCarrossel enviado acima!\n\nSalve as imagens e poste no Instagram.")

    except Exception as e:
        err = traceback.format_exc()
        log.error(f"Erro pipeline: {err}")
        await notify(bot, f"Erro no pipeline\n\n{str(e)[:300]}\n\nVerifique os logs no Railway.")
    finally:
        _pipeline_running = False


async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.message.chat.id != TELEGRAM_CHAT_ID:
        return
    data = query.data
    bot  = context.bot
    global _pipeline_running

    if data == "scout_retry":
        _pipeline_running = False
        asyncio.create_task(run_scout_step(bot, retry=True))
        return

    if data.startswith("trend_"):
        if _pipeline_running:
            await query.message.reply_text("Aguarde, o sistema ainda esta processando.")
            return
        index = int(data.split("_")[1])
        asyncio.create_task(run_pipeline_from_trend(index))


async def cmd_start(update, context):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    scheduler = context.bot_data.get("scheduler")
    job = scheduler.get_job("wavy_pipeline") if scheduler else None
    proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M") if job else "-"
    await update.message.reply_text(f"Wavy Content Bot\n\nComandos:\n/rodar - Executar pipeline\n/status - Status\n/ajuda - Ajuda\n\nProxima execucao: {proxima}", parse_mode=None)


async def cmd_rodar(update, context):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    if _pipeline_running:
        await update.message.reply_text("Pipeline ja esta rodando! Aguarde.")
        return
    await update.message.reply_text("Iniciando pipeline...\nVoce recebera atualizacoes a cada etapa!")
    asyncio.create_task(run_scout_step(context.bot, retry=False))


async def cmd_status(update, context):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    scheduler = context.bot_data.get("scheduler")
    job = scheduler.get_job("wavy_pipeline") if scheduler else None
    proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M") if job else "-"
    status = "Rodando agora" if _pipeline_running else "Aguardando"
    await update.message.reply_text(f"Status do Sistema\n\nBot: Online\nPipeline: {status}\nProxima execucao: {proxima}\nAgenda: Seg, Qua e Sex as 8h\nTemas vistos: {len(_shown_trend_titles)}", parse_mode=None)


async def cmd_ajuda(update, context):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    await update.message.reply_text("/rodar - Executar pipeline\n/status - Status do sistema\n/start - Boas-vindas\n/ajuda - Esta mensagem\n\nPipeline automatico: seg, qua e sex as 8h", parse_mode=None)


async def main():
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        lambda: asyncio.create_task(run_scout_step(Bot(token=TELEGRAM_TOKEN))),
        trigger=CronTrigger(day_of_week="mon,wed,fri", hour=8, minute=0, timezone="America/Sao_Paulo"),
        id="wavy_pipeline",
        name="Wavy Content Pipeline",
        replace_existing=True
    )
    scheduler.start()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.bot_data["scheduler"] = scheduler

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("rodar",  cmd_rodar))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ajuda",  cmd_ajuda))
    app.add_handler(CallbackQueryHandler(handle_callback))

    await app.bot.set_my_commands([
        BotCommand("rodar", "Executar pipeline agora"),
        BotCommand("status", "Ver status do sistema"),
        BotCommand("ajuda", "Ver todos os comandos"),
    ])

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    job = scheduler.get_job("wavy_pipeline")
    proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M")
    log.info(f"Sistema online - proxima execucao: {proxima}")

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"Wavy Content Bot online!\n\nSistema iniciado\nProxima execucao: {proxima}\n\n/rodar para rodar agora\n/status para ver status",
        parse_mode=None
    )

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
