"""
SCHEDULER - WAVY AGENTS
Conecta os 4 agentes, agenda execucao automatica 3x por semana,
e transmite progresso em tempo real via Telegram.
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot, Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from agent1_scout import run_scout
from agent2_strategist import run_strategist, set_template_escolhido, set_angulo_escolhido
from agent3_copywriter import run_copywriter, set_copy_decision
from agent4_designer import run_designer

# --- CONFIGURACOES ---
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)
log = logging.getLogger("wavy-scheduler")

# Estado global
_pipeline_running       = False
_shown_trend_titles: list[str] = []
_current_trends_data: dict     = {}


# --- UTILITARIO: envia status no Telegram ---

async def status(bot: Bot, msg: str):
    """Envia mensagem de progresso ao usuario."""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
    except Exception as e:
        log.warning(f"Falha ao enviar status: {e}")


# --- ENVIAR TRENDS ---

async def send_trends_to_telegram(bot: Bot, trends_data: dict):
    global _current_trends_data
    _current_trends_data = trends_data

    trends = trends_data.get("trends", [])
    if not trends:
        await status(bot, "Nenhuma trend encontrada. Tente novamente.")
        return

    texto = "*Top 5 trends de hoje:*\n\n"
    emojis = ["1", "2", "3", "4", "5"]
    for i, trend in enumerate(trends):
        texto += (
            f"{emojis[i]}. *{trend['titulo']}*\n"
            f"{trend['topico']} | {trend['score_viralidade']}/100\n"
            f"_{trend['descricao']}_\n\n"
        )

    botoes_escolha = [
        InlineKeyboardButton(emojis[i], callback_data=f"trend_{i}")
        for i in range(len(trends))
    ]
    botao_outros = InlineKeyboardButton("Buscar outros temas", callback_data="scout_retry")
    keyboard = InlineKeyboardMarkup([botoes_escolha, [botao_outros]])

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=texto,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# --- PIPELINE: SCOUT ---

async def run_full_pipeline(retry: bool = False):
    global _pipeline_running, _shown_trend_titles

    if _pipeline_running:
        log.warning("Pipeline ja esta rodando.")
        return

    _pipeline_running = True
    bot = Bot(token=TELEGRAM_TOKEN)
    now = datetime.now().strftime("%d/%m/%Y as %H:%M")

    try:
        if not retry:
            _shown_trend_titles = []
            await status(bot, f"Wavy iniciado! {now}\n\nAgente 1 - Scout\nColetando conteudo de 27 fontes (15 RSS + 12 Reddit)...")

        log.info("Agente 1 - Scout")
        trends_data = await run_scout(excluded_titles=_shown_trend_titles if _shown_trend_titles else None)

        if not trends_data.get("trends"):
            await status(bot, "Nenhuma trend encontrada hoje. Tente novamente mais tarde.")
            return

        count = len(trends_data["trends"])
        await status(bot, f"Scout concluido!\n{count} trends identificadas.\n\nEscolha uma trend abaixo:")

        for trend in trends_data.get("trends", []):
            titulo = trend.get("titulo", "")
            if titulo and titulo not in _shown_trend_titles:
                _shown_trend_titles.append(titulo)

        await send_trends_to_telegram(bot, trends_data)

    except Exception as e:
        log.error(f"Erro no pipeline Scout: {e}")
        await status(bot, f"Erro no Scout:\n{str(e)[:200]}")
    finally:
        _pipeline_running = False


# --- PIPELINE: AGENTES 2, 3, 4 ---

async def run_pipeline_from_trend(trend_index: int):
    global _pipeline_running, _current_trends_data

    _pipeline_running = True
    bot = Bot(token=TELEGRAM_TOKEN)

    try:
        trend = _current_trends_data.get("trends", [])[trend_index]

        # AGENTE 2 - run_strategist envia os botoes de template internamente
        # (apos reset, garantindo ordem correta)
        log.info("Agente 2 - Estrategista")
        final_choice = await run_strategist(_current_trends_data, selected_index=trend_index)
        if not final_choice:
            await status(bot, "Nenhum angulo escolhido. Pipeline cancelado.")
            return

        template = final_choice.get("template", "A")
        angulo   = final_choice.get("angulo", {})
        log.info(f"Template {template} | Angulo: {angulo.get('titulo','')}")

        # --- AGENTE 3: COPY ---
        await status(bot,
            f"Angulo escolhido:\n_{angulo.get('titulo','')}_ \n\n"
            f"Agente 3 - Copywriter\n"
            f"Pesquisando dados reais na web sobre o tema...\n"
            f"(pode levar ~1 min)"
        )
        log.info("Agente 3 - Copywriter: pesquisa")

        # Notifica quando a pesquisa termina e copy comeca
        async def notifica_gerando_copy():
            await asyncio.sleep(20)  # ~tempo da pesquisa web
            await status(bot, "Pesquisa concluida!\n\nGerando copy dos 10 slides com Claude...\n(pode levar ~1 min)")

        asyncio.create_task(notifica_gerando_copy())

        copy_result = await run_copywriter(final_choice)
        if not copy_result:
            await status(bot, "Erro ao gerar copy. Pipeline cancelado.")
            return

        slides_count = len(copy_result.get("copy", {}).get("slides", []))
        log.info(f"Copy gerada: {slides_count} slides")

        # --- AGENTE 4: DESIGNER ---
        await status(bot,
            f"Copy aprovada! {slides_count} slides.\n\n"
            f"Agente 4 - Designer\n"
            f"Gerando imagens no Freepik...\n"
            f"Slide a slide (3-5 min no total)"
        )
        log.info(f"Agente 4 - Designer (template {template})")

        png_paths = await run_designer(copy_result)

        await status(bot, f"Pipeline concluido!\n{len(png_paths)} slides gerados e enviados acima.")
        log.info(f"Pipeline concluido! {len(png_paths)} slides.")

    except Exception as e:
        log.error(f"Erro no pipeline (trend {trend_index}): {e}")
        await status(bot, f"Erro no pipeline:\n{str(e)[:300]}")
    finally:
        _pipeline_running = False


# --- CALLBACKS ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.message.chat.id != TELEGRAM_CHAT_ID:
        return

    data = query.data

    # Buscar outros temas
    if data == "scout_retry":
        global _pipeline_running
        _pipeline_running = False
        await query.message.reply_text("Buscando outros temas...\nAguarde!")
        context.application.create_task(run_full_pipeline(retry=True))
        return

    # Escolha de trend
    elif data.startswith("trend_"):
        if _pipeline_running:
            await query.message.reply_text("Aguarde, o sistema ainda esta processando.")
            return

        index = int(data.split("_")[1])
        trends = _current_trends_data.get("trends", [])

        if index >= len(trends):
            await query.message.reply_text("Trend nao encontrada.")
            return

        trend = trends[index]
        _pipeline_running = True

        await query.message.reply_text(
            f"Trend selecionada:\n*{trend['titulo']}*\n\nEscolha o template visual:",
            parse_mode="Markdown"
        )
        context.application.create_task(run_pipeline_from_trend(index))
        return

    # Escolha de template
    elif data.startswith("template_"):
        chosen = data.split("_")[1]
        nomes  = {"A": "Cinematico", "B": "Feed Claro", "C": "Editorial Escuro"}
        set_template_escolhido(chosen)
        await query.message.reply_text(
            f"Template {chosen} - {nomes.get(chosen, chosen)} selecionado!\n\nGerando angulos..."
        )
        return

    # Escolha de angulo
    elif data.startswith("angulo_"):
        try:
            with open("/tmp/angles_data.json", "r", encoding="utf-8") as f:
                angles_data = json.load(f)
            angulos = angles_data.get("angulos", [])
            index   = int(data.split("_")[1])
            if index < len(angulos):
                angulo = angulos[index]
                set_angulo_escolhido(angulo)
                await query.message.reply_text(
                    f"Angulo escolhido:\n*{angulo['titulo']}*\n\nIniciando pesquisa e copy...",
                    parse_mode="Markdown"
                )
        except Exception as e:
            log.error(f"Erro ao processar angulo: {e}")
            await query.message.reply_text("Erro ao processar escolha do angulo.")
        return

    # Aprovacao de copy
    elif data == "copy_approve":
        set_copy_decision("approve")
        await query.message.reply_text("Copy aprovada!\n\nIniciando geracao das artes...")
        return

    # Refazer copy
    elif data == "copy_redo":
        set_copy_decision("redo")
        await query.message.reply_text("Refazendo copy...\nAguarde.")
        return


# --- COMANDOS ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    scheduler = context.bot_data.get("scheduler")
    job = scheduler.get_job("wavy_pipeline") if scheduler else None
    proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M") if job else "-"
    await update.message.reply_text(
        f"*Wavy Content Bot*\n\n"
        f"/rodar - Executa o pipeline agora\n"
        f"/status - Ver status\n"
        f"/ajuda - Ver comandos\n\n"
        f"Proxima execucao automatica:\n*{proxima}*",
        parse_mode="Markdown"
    )


async def cmd_rodar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    if _pipeline_running:
        await update.message.reply_text("O pipeline ja esta rodando! Aguarde terminar.")
        return
    await update.message.reply_text("Iniciando pipeline...")
    context.application.create_task(run_full_pipeline())


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    scheduler = context.bot_data.get("scheduler")
    job = scheduler.get_job("wavy_pipeline") if scheduler else None
    proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M") if job else "-"
    status_txt = "Rodando agora" if _pipeline_running else "Aguardando"
    await update.message.reply_text(
        f"*Status do Sistema*\n\n"
        f"Bot: Online\n"
        f"Pipeline: {status_txt}\n"
        f"Proxima execucao: *{proxima}*\n"
        f"Agenda: Seg, Qua e Sex as 8h\n"
        f"Temas vistos hoje: *{len(_shown_trend_titles)}*",
        parse_mode="Markdown"
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    await update.message.reply_text(
        "*Comandos disponIveis*\n\n"
        "/rodar - Executa o pipeline agora\n"
        "/status - Status do sistema\n"
        "/start - Boas-vindas\n"
        "/ajuda - Esta mensagem\n\n"
        "_Roda automaticamente seg, qua e sex as 8h._",
        parse_mode="Markdown"
    )


# --- MAIN ---

def main():
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_full_pipeline,
        trigger=CronTrigger(
            day_of_week="mon,wed,fri",
            hour=8, minute=0,
            timezone="America/Sao_Paulo"
        ),
        id="wavy_pipeline",
        name="Wavy Content Pipeline",
        replace_existing=True
    )

    async def post_init(app: Application):
        scheduler.start()
        app.bot_data["scheduler"] = scheduler

        await app.bot.set_my_commands([
            BotCommand("rodar",  "Executar pipeline agora"),
            BotCommand("status", "Ver status do sistema"),
            BotCommand("ajuda",  "Ver todos os comandos"),
        ])

        job = scheduler.get_job("wavy_pipeline")
        proxima = job.next_run_time.strftime("%d/%m/%Y as %H:%M")
        log.info(f"Sistema online - proxima execucao: {proxima}")

        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                f"*Wavy Content Bot online!*\n\n"
                f"Proxima execucao automatica: *{proxima}*\n\n"
                f"/rodar para executar agora\n"
                f"/status para ver o status"
            ),
            parse_mode="Markdown"
        )

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("rodar",  cmd_rodar))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ajuda",  cmd_ajuda))
    app.add_handler(CallbackQueryHandler(handle_callback))

    log.info("Iniciando bot com run_polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
