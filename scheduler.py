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
from agent2_strategist import run_strategist, set_angulo_escolhido
from agent3_copywriter import run_copywriter, set_copy_decision
from agent4_designer import run_designer

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
log = logging.getLogger("wavy-scheduler")

_pipeline_running = False
_shown_trend_titles = []
_current_trends_data = {}
_current_trend_index = 0


async def notify(bot, text):
    log.info(text.replace("*","").replace("_",""))
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")
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
    texto = "*Top 5 trends de hoje:*\n\n"
    for i, trend in enumerate(trends):
        score = trend.get("score_viralidade", 0)
        texto += f"{emojis[i]}. *{trend['titulo']}*\n"
        texto += f"   {trend['topico']} - {score}/100\n"
        texto += f"   _{trend['descricao'][:100]}_\n\n"
    texto += "Escolha um tema ou busque outros:"

    botoes = [InlineKeyboardButton(emojis[i], callback_data=f"trend_{i}") for i in range(len(trends))]
    keyboard = InlineKeyboardMarkup([botoes, [InlineKeyboardButton("Buscar outros temas", callback_data="scout_retry")]])
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=texto, parse_mode="Markdown", reply_markup=keyboard)


async def run_scout_step(bot, retry=False):
    global _pipeline_running, _shown_trend_titles
    _pipeline_running = True
    now = datetime.now().strftime("%d/%m/%Y as %H:%M")
    try:
        if not retry:
            _shown_trend_titles = []
            await notify(bot,
                f"*Wavy Content Bot iniciado!*\n"
                f"Data: {now}\n\n"
                f"*Agente 1 - Scout*\n"
                f"Conectando nas fontes RSS e Reddit..."
            )
        else:
            await notify(bot,
                f"*Buscando outros temas...*\n\n"
                f"*Agente 1 - Scout*\n"
                f"Procurando tendencias diferentes das {len(_shown_trend_titles)} ja mostradas..."
            )

        trends_data = await run_scout(excluded_titles=_shown_trend_titles if _shown_trend_titles else None)

        if not trends_data.get("trends"):
            await notify(bot, "Nenhuma trend encontrada hoje. Tente novamente mais tarde.")
            return

        count = len(trends_data.get("trends", []))
        await notify(bot, f"*Scout concluido!*\n{count} tendencias encontradas\n\nPreparando lista para sua escolha...")

        for trend in trends_data.get("trends", []):
            titulo = trend.get("titulo", "")
            if titulo and titulo not in _shown_trend_titles:
                _shown_trend_titles.append(titulo)

        await send_trends_to_telegram(bot, trends_data)

    except Exception as e:
        err = traceback.format_exc()
        log.error(f"Erro Scout: {err}")
        await notify(bot, f"*Erro no Agente 1 - Scout*\n\n`{str(e)[:300]}`\n\nVerifique os logs no Railway.")
    finally:
        _pipeline_running = False


async def run_pipeline_from_trend(bot, trend_index):
    """Agentes 2, 3 e 4 a partir da trend selecionada."""
    global _pipeline_running, _current_trends_data, _current_trend_index
    _pipeline_running = True
    _current_trend_index = trend_index

    trends = _current_trends_data.get("trends", [])
    if trend_index >= len(trends):
        await notify(bot, "Trend nao encontrada. Rode /rodar novamente.")
        _pipeline_running = False
        return

    trend = trends[trend_index]

    try:
        #    AGENTE 2                                              
        await notify(bot,
            f"*Agente 2 - Estrategista*\n\n"
            f"Tema: *{trend['titulo']}*\n\n"
            f"Gerando 3 angulos diferentes para o carrossel...\n"
            f"_(Aguarde, isso leva alguns segundos)_"
        )

        final_choice = await run_strategist(_current_trends_data, selected_index=trend_index)

        if not final_choice:
            await notify(bot, "*Estrategista falhou ou timeout.*\n\nTente selecionar outro tema com /rodar.")
            return

        angulo_titulo = final_choice.get("angulo", {}).get("titulo", "")
        await notify(bot,
            f"*Estrategista concluido!*\n\n"
            f"Angulo escolhido:\n_{angulo_titulo}_\n\n"
            f"Passando para o Copywriter..."
        )

        #    AGENTE 3                                              
        await notify(bot,
            f"*Agente 3 - Copywriter*\n\n"
            f"Pesquisando dados reais sobre o tema na web...\n"
            f"Gerando copy completa para os 10 slides...\n\n"
            f"_(Isso pode levar 1-2 minutos)_"
        )

        copy_result = await run_copywriter(final_choice)

        if not copy_result:
            await notify(bot, "*Copywriter falhou.*\n\nVerifique os logs no Railway.")
            return

        slides_count = len(copy_result.get("copy", {}).get("slides", []))
        await notify(bot,
            f"*Copywriter concluido!*\n\n"
            f"{slides_count} slides escritos\n\n"
            f"Passando para o Designer..."
        )

        #    AGENTE 4                                              
        await notify(bot,
            f"*Agente 4 - Designer*\n\n"
            f"Gerando imagens no Freepik...\n"
            f"Renderizando slides em PNG 1080x1350px...\n\n"
            f"_(Isso pode levar 3-5 minutos)_"
        )

        png_paths = await run_designer(copy_result)

        await notify(bot,
            f"*Pipeline concluido com sucesso!*\n\n"
            f"{len(png_paths)} slides gerados e enviados acima!\n\n"
            f"_Salve as imagens e poste no Instagram._"
        )

        log.info(f"Pipeline concluido! {len(png_paths)} slides.")

    except Exception as e:
        err = traceback.format_exc()
        log.error(f"Erro pipeline: {err}")
        await notify(bot, f"*Erro no pipeline*\n\n`{str(e)[:300]}`\n\nVerifique os logs no Railway.")
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

    #    Buscar outros temas   
    if data == "scout_retry":
        _pipeline_running = False
        asyncio.create_task(run_scout_step(bot, retry=True))
        return

    #    Escolha de trend   
    if data.startswith("trend_"):
        if _pipeline_running:
            await query.message.reply_text("Aguarde, o sistema ainda esta processando.")
            return
        index = int(data.split("_")[1])
        asyncio.create_task(run_pipeline_from_trend(bot, index))
        return

    #    Escolha de angulo (chamado pelo Agente 2)   
    if data.startswith("angulo_"):
        import json
        try:
            with open("/tmp/angles_data.json", "r", encoding="utf-8") as f:
                angles_data = json.load(f)
            angulos = angles_data.get("angulos", [])
            index = int(data.split("_")[1])
            if index < len(angulos):
                angulo = angulos[index]
                await query.message.reply_text(
                    f"*Angulo aprovado!*\n\n"
                    f"_{angulo['titulo']}_\n\n"
                    f"Passando para o Copywriter...",
                    parse_mode="Markdown"
                )
                set_angulo_escolhido(angulo)
            else:
                await query.message.reply_text("Angulo nao encontrado. Tente novamente.")
        except Exception as e:
            log.error(f"Erro ao processar angulo: {e}")
            await query.message.reply_text(f"Erro ao processar angulo: {str(e)[:100]}")
        return

    # Aprovacao/refacao da copy (Agente 3)
    if data in ("copy_approve", "copy_redo"):
        if data == "copy_approve":
            await query.message.reply_text(
                "Copy aprovada! Passando para o Designer...\n(Isso pode levar 3-5 minutos)"
            )
        else:
            await query.message.reply_text("Refazendo a copy... Aguarde.")
        set_copy_decision(data.replace("copy_", ""))
        return


async def cmd_rodar(update, context):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    if _pipeline_running:
        await update.message.reply_text("Pipeline ja esta rodando! Aguarde terminar.")
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
    await update.message.reply_text(
        f"Status do Sistema\n\nBot: Online\nPipeline: {status}\nProxima execucao: {proxima}\nAgenda: Seg, Qua e Sex as 8h\nTemas vistos na sessao: {len(_shown_trend_titles)}",
        parse_mode=None
    )


async def cmd_ajuda(update, context):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    await update.message.reply_text(
        "/rodar - Executar pipeline\n/status - Status do sistema\n/ajuda - Esta mensagem\n\nPipeline automatico: seg, qua e sex as 8h",
        parse_mode=None
    )


async def cmd_start(update, context):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    scheduler = context.bot_data.get("scheduler")
    job = scheduler.get_job("wavy_pipeline") if scheduler else None
    proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M") if job else "-"
    await update.message.reply_text(
        f"Wavy Content Bot\n\n/rodar - Executar pipeline\n/status - Status\n/ajuda - Ajuda\n\nProxima execucao automatica: {proxima}",
        parse_mode=None
    )


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
        BotCommand("rodar",  "Executar pipeline agora"),
        BotCommand("status", "Ver status do sistema"),
        BotCommand("ajuda",  "Ver todos os comandos"),
    ])

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    job = scheduler.get_job("wavy_pipeline")
    proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M")
    log.info(f"Sistema online - proxima execucao: {proxima}")

    await app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"Wavy Content Bot online!\nProxima execucao: {proxima}\n\n/rodar para executar agora",
        parse_mode=None
    )

    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

# Alias para compatibilidade com o Start Command do Railway
run_full_pipeline = main
