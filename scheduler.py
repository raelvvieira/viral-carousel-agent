"""
SCHEDULER — PIPELINE MASTER
Orquestrador do pipeline completo de criação de conteúdo viral para Instagram.
Gerencia todas as etapas via Telegram bot:

  ETAPA 1 — Viral Scraper  (fonte → top 5 posts → usuário escolhe)
  ETAPA 2 — Research Agent (4-6 buscas → briefing → aprovação)
  ETAPA 3 — Formato        (carrossel / post único / reel)
  ETAPA 4 — Copy Agent v3  (copy nova → aprovação)
  ETAPA 5 — Image Agent v2 (imagens slide a slide → aprovação)
  ETAPA 6 — Designer v3    (HTML → Playwright → álbum Telegram)
"""

import os
import json
import asyncio
import logging
from datetime import datetime

from telegram import (
    Bot, Update, BotCommand,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

from agent1_viral_scraper import (
    run_viral_scraper, analisar_post_selecionado,
    listar_perfis, adicionar_perfil, remover_perfil, carregar_base_perfis
)
from agent2_research import run_research
from agent3_copy import run_copy_agent, ajustar_slide
from agent4_image import run_image_agent, trocar_imagem
from agent5_designer import run_designer

# ── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)
log = logging.getLogger("wavy-pipeline")

# ── ESTADO GLOBAL DO PIPELINE ────────────────────────────────────────────────
_estado = {
    "etapa_atual": None,       # "scraper" | "research" | "formato" | "copy" | "imagens" | "design" | None
    "rodando": False,
    "viral_payload": None,
    "briefing_payload": None,
    "formato": None,
    "num_slides": 7,
    "copy_payload": None,
    "image_payload": None,
    "template": "A",
    "perfil": {
        "nome": "wavy",
        "handle": "@wavy.mkt",
        "foto_url": "https://i.ibb.co/bMtB5PZL/488223687-8876273612474124-8754739128155263998-n.jpg"
    },
    "aguardando_input": None,  # chave do input esperado
    "post_index_atual": None,  # índice do post selecionado (para retry de copy)
    "copy_retry_usado": False, # True após primeira releitura (só 1 retry permitido)
}

_perfil_path = "/tmp/wavy_perfil.json"


# ── PERSISTÊNCIA DO PERFIL ───────────────────────────────────────────────────

def carregar_perfil():
    try:
        with open(_perfil_path, "r") as f:
            _estado["perfil"] = json.load(f)
    except Exception:
        pass


def salvar_perfil():
    with open(_perfil_path, "w") as f:
        json.dump(_estado["perfil"], f, ensure_ascii=False)


# ── HELPERS ──────────────────────────────────────────────────────────────────

async def msg(bot: Bot, texto: str, parse_mode: str = "Markdown"):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=texto, parse_mode=parse_mode)
    except Exception as e:
        log.warning(f"Falha ao enviar mensagem: {e}")


def kb(*botoes: list) -> InlineKeyboardMarkup:
    """Atalho para criar InlineKeyboardMarkup."""
    return InlineKeyboardMarkup(botoes)


def resetar_estado():
    _estado.update({
        "etapa_atual": None, "rodando": False,
        "viral_payload": None, "briefing_payload": None,
        "formato": None, "num_slides": 7,
        "copy_payload": None, "image_payload": None,
        "template": "A", "aguardando_input": None,
        "post_index_atual": None, "copy_retry_usado": False,
    })


# ── ETAPA 0: CHECAR PERFIL ───────────────────────────────────────────────────

async def verificar_perfil(bot: Bot) -> bool:
    """Retorna True se o perfil está configurado."""
    p = _estado["perfil"]
    if p["nome"] and p["handle"]:
        return True

    await msg(bot,
        "👤 *Primeira vez aqui!*\n\n"
        "Para personalizar os posts com sua identidade, preciso de:\n"
        "• Seu nome (ex: Rael Costa)\n"
        "• Seu @handle (ex: @raelcosta)\n"
        "• URL da sua foto de perfil\n\n"
        "_Digite seu nome agora:_"
    )
    _estado["aguardando_input"] = "perfil_nome"
    return False


# ── ETAPA 1: VIRAL SCRAPER ───────────────────────────────────────────────────

async def iniciar_pipeline(bot: Bot):
    """Passo inicial: pergunta a fonte do post viral."""
    _estado["etapa_atual"] = "scraper"
    await msg(bot,
        "🚀 *Wavy Pipeline iniciado!*\n\n"
        "De onde quer buscar o post viral de referência?\n",
        parse_mode="Markdown"
    )
    keyboard = kb(
        [
            InlineKeyboardButton("📋 1. Minha base de perfis", callback_data="fonte_1"),
            InlineKeyboardButton("🔍 2. Tema", callback_data="fonte_2"),
        ],
        [
            InlineKeyboardButton("🔗 3. Link direto", callback_data="fonte_3"),
            InlineKeyboardButton("🔥 4. Top viral geral", callback_data="fonte_4"),
        ]
    )
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="Escolha a fonte:",
        reply_markup=keyboard
    )


async def executar_scraper(bot: Bot, fonte: int, **kwargs):
    """Roda o Viral Scraper e exibe o ranking para o usuário escolher."""
    if fonte == 1:
        perfis = carregar_base_perfis()
        lista_txt = "  ·  ".join(perfis) if perfis else "(nenhum perfil cadastrado)"
        await msg(bot, f"🔍 Buscando posts em {len(perfis)} perfis:\n{lista_txt}", parse_mode=None)

        loop = asyncio.get_event_loop()

        def progress_cb(handle, count, views):
            if count > 0:
                views_txt = f" · melhor: {views/1000:.0f}K views" if views > 0 else ""
                text = f"✅ {handle} — {count} post{'s' if count != 1 else ''}{views_txt}"
            else:
                text = f"⚠️ {handle} — sem posts recentes"
            asyncio.run_coroutine_threadsafe(msg(bot, text, parse_mode=None), loop)

        kwargs["progress_cb"] = progress_cb
    else:
        await msg(bot, f"🔍 Buscando posts virais... (fonte {fonte})")

    try:
        resultado = await asyncio.to_thread(run_viral_scraper, fonte, **kwargs)
    except Exception as e:
        await msg(bot, f"❌ Erro no Scraper: {str(e)[:200]}")
        resetar_estado()
        return

    posts = resultado.get("posts", [])
    if not posts:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="😕 Nenhum post encontrado com essa fonte. Quer tentar outra?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Tentar outra fonte", callback_data="scraper_retry")]
            ])
        )
        _estado["rodando"] = False
        _estado["etapa_atual"] = None
        return

    _estado["etapa_atual"] = "escolha_post"
    _estado["total_posts_disponiveis"] = len(posts)
    ranking = resultado.get("ranking_txt", "")
    await msg(bot, ranking, parse_mode=None)

    # Gera um botão por post (até 10), 2 por linha
    linhas_botoes = []
    for i, post in enumerate(posts[:10]):
        tipo_raw = (post.get("type") or post.get("productType") or "").lower()
        if "video" in tipo_raw or "reel" in tipo_raw:
            emoji = "📹"
        elif "sidecar" in tipo_raw or "carousel" in tipo_raw:
            emoji = "📑"
        else:
            emoji = "🖼️"
        autor = (post.get("ownerUsername") or post.get("username") or "?")[:12]
        btn = InlineKeyboardButton(f"#{i+1} {emoji} @{autor}", callback_data=f"post_{i}")
        if i % 2 == 0:
            linhas_botoes.append([btn])
        else:
            linhas_botoes[-1].append(btn)

    linhas_botoes.append([InlineKeyboardButton("🔄 Buscar outros", callback_data="scraper_retry")])

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="Qual post quer usar como referência?",
        reply_markup=InlineKeyboardMarkup(linhas_botoes)
    )


def _formatar_copy_completa(post: dict) -> list[str]:
    """
    Monta a copy completa do post em blocos de texto.
    Retorna lista de strings prontas para enviar (já particionadas pelo limite do Telegram).
    """
    copy = post.get("copy", {})
    tipo = post.get("tipo", "")
    metricas = post.get("metricas", {})

    cabecalho = (
        f"📌 *{post.get('autor', '?')}*  ·  {tipo.upper()}\n"
        f"📊 {metricas.get('likes', 0)} likes · {metricas.get('views', 0)} views · "
        f"{metricas.get('engajamento_pct', 0):.1f}% eng\n"
        f"─────────────────────────\n"
    )

    blocos = [cabecalho]

    legenda = copy.get("legenda", "").strip()
    if legenda:
        blocos.append(f"📝 *Legenda:*\n{legenda}")

    transcricao = (copy.get("transcricao") or "").strip()
    status_tr = (copy.get("status") or {}).get("transcricao", "")
    if transcricao:
        blocos.append(f"🎙️ *Transcrição:*\n{transcricao}")
    elif tipo == "reel":
        motivo = {
            "sem_fala_detectada": "sem fala detectada no áudio",
            "erro_api": "API de transcrição falhou — tente reler",
            "ausente": "URL do reel não encontrada",
        }.get(status_tr, status_tr or "não disponível")
        blocos.append(f"🎙️ *Transcrição:* _(vazia — {motivo})_")

    texto_visual = (copy.get("texto_visual") or "").strip()
    if texto_visual:
        blocos.append(f"👁️ *Texto visual:*\n{texto_visual}")

    slides = copy.get("slides") or []
    if slides:
        slides_txt = "\n".join(
            f"*Slide {i+1}:* {s}" if isinstance(s, str) else
            f"*Slide {i+1}:* {s.get('texto','')}"
            for i, s in enumerate(slides)
        )
        blocos.append(f"📑 *Slides:*\n{slides_txt}")

    if not any([legenda, transcricao, texto_visual, slides]):
        blocos.append("_(nenhum texto detectado)_")

    # Junta tudo e particiona em fatias de 4000 chars (limite Telegram)
    full = "\n\n".join(blocos)
    partes = [full[i:i+4000] for i in range(0, len(full), 4000)]
    return partes


async def analisar_post_escolhido(bot: Bot, post_index: int):
    """Extrai copy completa do post escolhido e aguarda confirmação do usuário."""
    _estado["post_index_atual"] = post_index
    _estado["copy_retry_usado"] = False

    tipo_label = {
        "reel": ("📹 Reel", "transcrevendo áudio via API", "30–60s"),
        "carrossel": ("📑 Carrossel", "lendo cada slide via OCR", "20–40s"),
        "post_estatico": ("🖼️ Post único", "lendo texto da imagem via OCR", "5–10s"),
    }

    try:
        # Pega o tipo do post direto do cache (sem chamar API nenhuma)
        tipo_detectado = "?"
        num_slides = 0
        try:
            with open("/tmp/wavy_viral_posts.json", "r", encoding="utf-8") as f:
                posts_cache = json.load(f)
            if 0 <= post_index < len(posts_cache):
                item = posts_cache[post_index]
                tipo_raw = (item.get("type") or item.get("productType") or "").lower()
                if "video" in tipo_raw or "reel" in tipo_raw:
                    tipo_detectado = "reel"
                elif "sidecar" in tipo_raw or "carousel" in tipo_raw:
                    tipo_detectado = "carrossel"
                    slides = item.get("childPosts") or item.get("sidecarChildren") or []
                    num_slides = len(slides)
                else:
                    tipo_detectado = "post_estatico"
        except Exception:
            pass

        emoji, acao, tempo = tipo_label.get(tipo_detectado, ("🔬", "extraindo copy", "30s"))
        detalhe = f" ({num_slides} slides)" if tipo_detectado == "carrossel" and num_slides else ""

        await msg(bot,
            f"🔬 *Post #{post_index + 1} selecionado* — {emoji}{detalhe}\n\n"
            f"⏳ {acao}...\n"
            f"_Tempo estimado: {tempo} — aguarde_"
        )

        try:
            payload = await asyncio.to_thread(analisar_post_selecionado, post_index)
        except Exception as e:
            await msg(bot, f"❌ Erro ao analisar post: {str(e)[:200]}")
            return

        if "erro" in payload:
            await msg(bot, f"❌ {payload['erro']}")
            return

        _estado["viral_payload"] = payload
        post = payload.get("post_viral", {})

        tipo_final = post.get("tipo", tipo_detectado)
        _, acao_final, _ = tipo_label.get(tipo_final, ("🔬", tipo_final, ""))
        await msg(bot, f"✅ *Copy extraída com sucesso!* _{acao_final.replace('indo', 'ída').replace('lendo', 'lida')}_\n\nAqui está tudo que foi capturado:")

        # Envia copy completa sem truncar nada
        for parte in _formatar_copy_completa(post):
            await msg(bot, parte)

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="A copy captada está completa?",
            reply_markup=kb(
                [
                    InlineKeyboardButton("✅ Copy ok — iniciar pesquisa", callback_data="copy_leitura_ok"),
                    InlineKeyboardButton("🔄 Reler copy", callback_data="copy_reler"),
                ],
                [
                    InlineKeyboardButton("↩️ Escolher outro post", callback_data="scraper_retry"),
                ]
            )
        )

    except Exception as e:
        log.error(f"[PIPELINE] Erro em analisar_post_escolhido: {e}", exc_info=True)
        _estado["rodando"] = False
        await msg(bot, f"❌ Erro inesperado ao processar post #{post_index + 1}: {str(e)[:200]}\n\nTente outro post ou use /cancelar.")


async def analisar_post_escolhido_retry(bot: Bot, post_index: int):
    """Releitura da copy do post (chamada apenas na 2ª tentativa)."""
    try:
        try:
            payload = await asyncio.to_thread(analisar_post_selecionado, post_index)
        except Exception as e:
            await msg(bot, f"❌ Erro ao reler post: {str(e)[:200]}")
            return

        if "erro" in payload:
            await msg(bot, f"❌ {payload['erro']}")
            return

        _estado["viral_payload"] = payload
        post = payload.get("post_viral", {})

        await msg(bot, "🔄 *Releitura concluída — nova copy captada:*")
        for parte in _formatar_copy_completa(post):
            await msg(bot, parte)

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="Agora a copy está completa?",
            reply_markup=kb(
                [
                    InlineKeyboardButton("✅ Copy ok — iniciar pesquisa", callback_data="copy_leitura_ok"),
                    InlineKeyboardButton("🔄 Reler copy", callback_data="copy_reler"),
                ],
                [
                    InlineKeyboardButton("↩️ Escolher outro post", callback_data="scraper_retry"),
                ]
            )
        )

    except Exception as e:
        log.error(f"[PIPELINE] Erro em analisar_post_escolhido_retry: {e}", exc_info=True)
        await msg(bot, f"❌ Erro inesperado na releitura: {str(e)[:200]}\n\nTente outro post ou use /cancelar.")


# ── ETAPA 2: RESEARCH AGENT ──────────────────────────────────────────────────

async def executar_research(bot: Bot):
    """Roda o Research Agent e apresenta o resumo da pesquisa."""
    try:
        _estado["etapa_atual"] = "research"
        await msg(bot, "🔍 *Research Agent iniciado!*\n\nRealizando 5 buscas web sobre o tema...\n_(pode levar ~1 min)_")
        try:
            payload = await asyncio.to_thread(run_research, _estado["viral_payload"])
        except Exception as e:
            _estado["rodando"] = False
            await msg(bot, f"❌ Erro no Research: {str(e)[:200]}\n\nUse /cancelar para reiniciar.")
            return

        if "erro" in payload:
            _estado["rodando"] = False
            await msg(bot, f"❌ {payload['erro']}\n\nUse /cancelar para reiniciar.")
            return

        _estado["briefing_payload"] = payload
        resumo = payload.get("resumo_pesquisa", "")
        tema = payload.get("tema_central", "")

        await msg(bot,
            f"🔍 *Pesquisa concluída!*\n\n"
            f"*Tema:* {tema}\n\n"
            f"{resumo}\n\n"
            f"─────────────────────────\n"
            f"Copy completa + resumo da pesquisa salvos. Pronto para o próximo agente."
        )
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="Próxima etapa:",
            reply_markup=kb(
                [
                    InlineKeyboardButton("✅ Próxima etapa", callback_data="briefing_ok"),
                    InlineKeyboardButton("🔄 Refazer pesquisa", callback_data="research_retry"),
                ]
            )
        )

    except Exception as e:
        log.error(f"[PIPELINE] Erro em executar_research: {e}", exc_info=True)
        _estado["rodando"] = False
        await msg(bot, f"❌ Erro inesperado na pesquisa: {str(e)[:200]}\n\nUse /cancelar para reiniciar.")


# ── ETAPA 3: ESCOLHA DO FORMATO ──────────────────────────────────────────────

async def perguntar_formato(bot: Bot):
    """Pergunta o formato de saída entre Research e Copy."""
    _estado["etapa_atual"] = "formato"
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="📐 *Qual formato você quer para esse conteúdo?*",
        parse_mode="Markdown",
        reply_markup=kb(
            [
                InlineKeyboardButton("📑 Carrossel (7 slides)", callback_data="fmt_carrossel_7"),
                InlineKeyboardButton("📑 Carrossel (10 slides)", callback_data="fmt_carrossel_10"),
            ],
            [
                InlineKeyboardButton("🖼️ Post único", callback_data="fmt_post_unico"),
                InlineKeyboardButton("🎬 Roteiro de Reel", callback_data="fmt_reel"),
            ]
        )
    )


# ── ETAPA 4: COPY AGENT ──────────────────────────────────────────────────────

async def executar_copy(bot: Bot):
    """Roda o Copy Agent e apresenta para aprovação."""
    _estado["etapa_atual"] = "copy"
    fmt = _estado.get("formato", "carrossel")
    num = _estado.get("num_slides", 7)
    await msg(bot,
        f"✍️ *Copy Agent v3 iniciado!*\n\n"
        f"Formato: {fmt.replace('_', ' ').title()} · {num} slides\n\n"
        f"Gerando copy inspirada no viral com dados da pesquisa...\n_(pode levar ~1 min)_"
    )
    try:
        payload = await asyncio.to_thread(
            run_copy_agent, _estado["briefing_payload"], fmt, num
        )
    except Exception as e:
        _estado["rodando"] = False
        await msg(bot, f"❌ Erro na Copy: {str(e)[:200]}\n\nUse /cancelar para reiniciar.")
        return

    if "erro" in payload:
        _estado["rodando"] = False
        await msg(bot, f"❌ {payload['erro']}\n\nUse /cancelar para reiniciar.")
        return

    _estado["copy_payload"] = payload
    copy_data = payload.get("copy_aprovada", {})
    copy_txt = copy_data.get("copy_formatada", "")

    # Envia em partes se muito longa
    partes = [copy_txt[i:i+3500] for i in range(0, len(copy_txt), 3500)]
    for parte in partes:
        await msg(bot, parte)

    if fmt == "reel":
        # Reel: sem imagens nem designer
        await msg(bot,
            "🎬 *Roteiro pronto!*\n\n"
            "O roteiro acima é para você gravar e editar.\n\n"
            "─────────────────────────\n"
            "🏁 *Pipeline completo!* Quer ajustar algum bloco?"
        )
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="O que fazer?",
            reply_markup=kb(
                [
                    InlineKeyboardButton("✅ Perfeito!", callback_data="copy_ok_reel"),
                    InlineKeyboardButton("✏️ Ajustar um bloco", callback_data="copy_ajustar"),
                ],
                [
                    InlineKeyboardButton("🔄 Refazer", callback_data="copy_redo"),
                    InlineKeyboardButton("📐 Outro formato", callback_data="copy_outro_formato"),
                ]
            )
        )
        return

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="Como ficou a copy?",
        reply_markup=kb(
            [
                InlineKeyboardButton("✅ Aprovado — buscar imagens", callback_data="copy_ok"),
                InlineKeyboardButton("✏️ Ajustar slide", callback_data="copy_ajustar"),
            ],
            [
                InlineKeyboardButton("🔄 Refazer com outro ângulo", callback_data="copy_redo"),
                InlineKeyboardButton("📐 Outro formato", callback_data="copy_outro_formato"),
            ]
        )
    )


# ── ETAPA 5: IMAGE AGENT ─────────────────────────────────────────────────────

async def executar_images(bot: Bot):
    """Roda o Image Agent e apresenta URLs para aprovação."""
    _estado["etapa_atual"] = "imagens"
    copy_data = (_estado.get("copy_payload") or {}).get("copy_aprovada", {})
    total_slides = len(copy_data.get("slides", []))
    await msg(bot,
        f"🖼️ *Image Agent v2 iniciado!*\n\n"
        f"Buscando imagens para {total_slides} slides...\n"
        f"Fontes: Freepik IA → Google Images → Pexels/Unsplash\n\n"
        f"_(pode levar 2–4 min)_"
    )
    try:
        payload = await asyncio.to_thread(run_image_agent, _estado["copy_payload"])
    except Exception as e:
        _estado["rodando"] = False
        await msg(bot, f"❌ Erro no Image Agent: {str(e)[:200]}\n\nUse /cancelar para reiniciar.")
        return

    if "erro" in payload:
        _estado["rodando"] = False
        await msg(bot, f"❌ {payload['erro']}\n\nUse /cancelar para reiniciar.")
        return

    _estado["image_payload"] = payload
    aprovacao_txt = payload.get("aprovacao_txt", "")
    ok = payload.get("imagens_ok", 0)
    total = payload.get("total_imagens", 0)

    await msg(bot, aprovacao_txt[:3500])
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"✅ {ok}/{total} imagens encontradas. Aprovado?",
        reply_markup=kb(
            [
                InlineKeyboardButton("✅ Aprovado — montar slides", callback_data="images_ok"),
                InlineKeyboardButton("🔄 Trocar uma imagem", callback_data="images_trocar"),
            ]
        )
    )


# ── ETAPA 6: DESIGNER AGENT ──────────────────────────────────────────────────

async def perguntar_template(bot: Bot):
    """Pergunta o template visual antes de renderizar."""
    _estado["etapa_atual"] = "template"
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🎨 *Qual template visual?*\n\n"
            "🅰️ Template A — Dark Cinematográfico (fundo preto, tipografia grande)\n"
            "🅱️ Template B — Light Twitter Style (fundo cinza claro, cards)\n"
            "©️ Template C — Editorial Escuro (preto total, imagem full-bleed no cover)"
        ),
        parse_mode="Markdown",
        reply_markup=kb(
            [
                InlineKeyboardButton("🅰️ Template A", callback_data="template_A"),
                InlineKeyboardButton("🅱️ Template B", callback_data="template_B"),
                InlineKeyboardButton("©️ Template C", callback_data="template_C"),
            ]
        )
    )


async def executar_designer(bot: Bot):
    """Roda o Designer Agent — renderiza e envia slides."""
    _estado["etapa_atual"] = "design"
    template = _estado.get("template", "A")
    perfil   = _estado.get("perfil", {})
    await msg(bot,
        f"🎨 *Designer Agent v3 iniciado!*\n\n"
        f"Template: {template}\n"
        f"Renderizando slides com Playwright...\n\n"
        f"_(cada slide aparece aqui para você acompanhar)_"
    )
    try:
        pngs = await run_designer(_estado["image_payload"], template, perfil)
    except Exception as e:
        await msg(bot, f"❌ Erro no Designer: {str(e)[:200]}")
        return

    await msg(bot,
        f"🏁 *Pipeline completo!*\n\n"
        f"✅ {len(pngs)} slides entregues acima.\n\n"
        f"Use /rodar para criar outro conteúdo."
    )
    resetar_estado()


# ── HANDLERS DE CALLBACK ─────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.message.chat.id != TELEGRAM_CHAT_ID:
        return

    bot  = context.bot
    data = query.data

    # ── Escolha de fonte ──
    if data.startswith("fonte_"):
        fonte = int(data.split("_")[1])
        if fonte == 2:
            await msg(bot, "🔍 Qual tema você quer pesquisar? _(ex: Meta Ads, IA, Produtividade)_")
            _estado["aguardando_input"] = "tema_scraper"
            return
        if fonte == 3:
            await msg(bot, "🔗 Cole o link do post ou perfil que quer analisar:")
            _estado["aguardando_input"] = "link_scraper"
            return
        context.application.create_task(executar_scraper(bot, fonte))

    # ── Scraper retry ──
    elif data == "scraper_retry":
        await iniciar_pipeline(bot)

    # ── Escolha de post ──
    elif data.startswith("post_"):
        idx = int(data.split("_")[1])
        context.application.create_task(analisar_post_escolhido(bot, idx))

    # ── Copy leitura confirmada — avança para research ──
    elif data == "copy_leitura_ok":
        context.application.create_task(executar_research(bot))

    # ── Reler copy (apenas 1 tentativa extra) ──
    elif data == "copy_reler":
        idx = _estado.get("post_index_atual")
        if idx is None:
            await msg(bot, "❌ Post não encontrado. Reinicie com /rodar.")
            return
        if _estado["copy_retry_usado"]:
            await msg(bot,
                "⚠️ Já tentei reler essa copy uma vez.\n\n"
                "Se ainda estiver incompleta, pode ser limitação da API para esse conteúdo.\n"
                "Quer avançar mesmo assim ou escolher outro post?"
            )
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text="Como quer continuar?",
                reply_markup=kb(
                    [
                        InlineKeyboardButton("✅ Avançar mesmo assim", callback_data="copy_leitura_ok"),
                        InlineKeyboardButton("↩️ Escolher outro post", callback_data="scraper_retry"),
                    ]
                )
            )
            return
        _estado["copy_retry_usado"] = True
        await msg(bot, "🔄 Relendo a copy do post... _(tentativa extra)_")
        context.application.create_task(analisar_post_escolhido_retry(bot, idx))

    # ── Research retry ──
    elif data == "research_retry":
        context.application.create_task(executar_research(bot))

    # ── Briefing aprovado ──
    elif data == "briefing_ok":
        await perguntar_formato(bot)

    # ── Formato escolhido ──
    elif data.startswith("fmt_"):
        partes = data.split("_")
        if "carrossel" in data:
            _estado["formato"] = "carrossel"
            _estado["num_slides"] = int(partes[-1]) if partes[-1].isdigit() else 7
        elif "post" in data:
            _estado["formato"] = "post_unico"
            _estado["num_slides"] = 1
        elif "reel" in data:
            _estado["formato"] = "reel"
            _estado["num_slides"] = 0
        context.application.create_task(executar_copy(bot))

    # ── Copy aprovada (carrossel/post) ──
    elif data == "copy_ok":
        context.application.create_task(executar_images(bot))

    # ── Copy aprovada (reel) ──
    elif data == "copy_ok_reel":
        resetar_estado()
        await msg(bot, "✅ Perfeito! Use /rodar para criar outro conteúdo.")

    # ── Copy: ajustar slide ──
    elif data == "copy_ajustar":
        await msg(bot, "✏️ Qual slide quer ajustar e o que mudar?\n_(ex: \"slide 3 — deixa mais agressivo\")_")
        _estado["aguardando_input"] = "copy_ajuste"

    # ── Copy: refazer ──
    elif data == "copy_redo":
        context.application.create_task(executar_copy(bot))

    # ── Copy: tentar outro formato (reutiliza briefing_payload, sem reiniciar pipeline) ──
    elif data == "copy_outro_formato":
        await perguntar_formato(bot)

    # ── Imagens aprovadas ──
    elif data == "images_ok":
        await perguntar_template(bot)

    # ── Trocar imagem ──
    elif data == "images_trocar":
        await msg(bot, "🔄 Qual slide quer trocar? _(ex: \"slide 3\")_\nOu descreva a imagem ideal.")
        _estado["aguardando_input"] = "image_troca"

    # ── Template escolhido ──
    elif data.startswith("template_"):
        _estado["template"] = data.split("_")[1]
        context.application.create_task(executar_designer(bot))


# ── HANDLER DE MENSAGENS DE TEXTO ────────────────────────────────────────────

async def handle_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return

    bot   = context.bot
    texto = update.message.text.strip()
    esperando = _estado.get("aguardando_input")

    if not esperando:
        return

    # ── Cadastro de perfil ──
    if esperando == "perfil_nome":
        _estado["perfil"]["nome"] = texto
        await msg(bot, f"✅ Nome: *{texto}*\n\nAgora seu @handle:")
        _estado["aguardando_input"] = "perfil_handle"

    elif esperando == "perfil_handle":
        handle = texto if texto.startswith("@") else f"@{texto}"
        _estado["perfil"]["handle"] = handle
        await msg(bot, f"✅ Handle: *{handle}*\n\nURL da sua foto de perfil (ou 'pular'):")
        _estado["aguardando_input"] = "perfil_foto"

    elif esperando == "perfil_foto":
        if texto.lower() not in ("pular", "skip", "-"):
            _estado["perfil"]["foto_url"] = texto
        salvar_perfil()
        await msg(bot,
            f"✅ Perfil salvo!\n"
            f"Nome: {_estado['perfil']['nome']}\n"
            f"Handle: {_estado['perfil']['handle']}\n\n"
            f"Iniciando pipeline..."
        )
        _estado["aguardando_input"] = None
        await iniciar_pipeline(bot)

    # ── Tema para scraper ──
    elif esperando == "tema_scraper":
        _estado["aguardando_input"] = None
        context.application.create_task(executar_scraper(bot, fonte=2, tema=texto))

    # ── Link direto para scraper ──
    elif esperando == "link_scraper":
        _estado["aguardando_input"] = None
        context.application.create_task(executar_scraper(bot, fonte=3, url=texto))

    # ── Ajuste de copy ──
    elif esperando == "copy_ajuste":
        _estado["aguardando_input"] = None
        partes = texto.lower().split()
        slide_num = None
        for i, p in enumerate(partes):
            if p.isdigit():
                slide_num = int(p)
                break

        if slide_num and _estado.get("copy_payload"):
            await msg(bot, f"✏️ Ajustando slide {slide_num}...")
            instrucao = texto
            payload_atualizado = await asyncio.to_thread(
                ajustar_slide, _estado["copy_payload"]["copy_aprovada"], slide_num, instrucao
            )
            _estado["copy_payload"]["copy_aprovada"] = payload_atualizado
            await msg(bot, f"✅ Slide {slide_num} atualizado!\n\n{payload_atualizado.get('slides', [])[slide_num-1] if payload_atualizado.get('slides') else ''}")
        else:
            await msg(bot, "❌ Não encontrei o número do slide. Tente: \"slide 3 — mais agressivo\"")
        return

    # ── Troca de imagem ──
    elif esperando == "image_troca":
        _estado["aguardando_input"] = None
        partes = texto.lower().split()
        slide_num = None
        for p in partes:
            if p.isdigit():
                slide_num = int(p)
                break

        if slide_num and _estado.get("image_payload"):
            await msg(bot, f"🔄 Trocando imagem do slide {slide_num}...")
            imagens = _estado["image_payload"].get("imagens_aprovadas", [])
            imagens_novas = await asyncio.to_thread(trocar_imagem, imagens, slide_num, texto)
            _estado["image_payload"]["imagens_aprovadas"] = imagens_novas

            img = next((i for i in imagens_novas if i["slide_num"] == slide_num), {})
            await msg(bot,
                f"✅ Slide {slide_num} atualizado!\n"
                f"Fonte: {img.get('fonte', '?')}\n"
                f"{img.get('url', '—')}"
            )
        else:
            await msg(bot, "❌ Não encontrei o número do slide. Tente: \"slide 3\"")
        return

    # ── Gestão da base de perfis ──
    elif esperando == "base_adicionar":
        _estado["aguardando_input"] = None
        resultado = adicionar_perfil(texto)
        await msg(bot, resultado["msg"])

    elif esperando == "base_remover":
        _estado["aguardando_input"] = None
        resultado = remover_perfil(texto)
        await msg(bot, resultado["msg"])


# ── COMANDOS ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    await update.message.reply_text(
        "*Wavy Content Bot* 🌊\n\n"
        "/rodar — Inicia o pipeline completo\n"
        "/status — Ver status atual\n"
        "/base — Gerenciar base de perfis\n"
        "/ajuda — Todos os comandos\n\n"
        "_Sistema de criação de conteúdo viral para Instagram_",
        parse_mode="Markdown"
    )


async def cmd_rodar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    if _estado["rodando"]:
        await update.message.reply_text("⏳ Pipeline já está rodando! Aguarde terminar.")
        return
    _estado["rodando"] = True
    carregar_perfil()
    bot = context.bot
    if not await verificar_perfil(bot):
        return  # perfil sendo coletado via handle_texto
    await iniciar_pipeline(bot)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    etapa = _estado.get("etapa_atual") or "aguardando"
    rodando = "🔄 Rodando" if _estado["rodando"] else "⏸️ Aguardando"
    perfil = _estado.get("perfil", {})
    await update.message.reply_text(
        f"*Status do Pipeline*\n\n"
        f"Bot: Online ✅\n"
        f"Pipeline: {rodando}\n"
        f"Etapa atual: *{etapa}*\n\n"
        f"Perfil configurado: {'✅' if perfil.get('nome') else '❌'}\n"
        f"Nome: {perfil.get('nome', '—')}\n"
        f"Handle: {perfil.get('handle', '—')}",
        parse_mode="Markdown"
    )


async def cmd_base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    from agent1_viral_scraper import listar_perfis
    info = listar_perfis()
    perfis = info.get("perfis", [])
    lista = "\n".join(perfis) if perfis else "_Base vazia_"
    await update.message.reply_text(
        f"📋 *Base de perfis* ({info['total']}/10)\n\n{lista}",
        parse_mode="Markdown",
        reply_markup=kb(
            [
                InlineKeyboardButton("➕ Adicionar perfil", callback_data="base_add"),
                InlineKeyboardButton("➖ Remover perfil", callback_data="base_remove"),
            ]
        )
    )


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    resetar_estado()
    await update.message.reply_text("✅ Pipeline cancelado. Use /rodar para começar de novo.")


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    await update.message.reply_text(
        "*Comandos disponíveis*\n\n"
        "/rodar — Inicia o pipeline completo\n"
        "/status — Ver etapa atual\n"
        "/base — Gerenciar base de perfis\n"
        "/cancelar — Cancela o pipeline atual\n"
        "/ajuda — Esta mensagem\n\n"
        "*Retomadas parciais:*\n"
        "_\"refaz só a copy\"_ — pula para etapa 4\n"
        "_\"troca as imagens\"_ — pula para etapa 5\n"
        "_\"refaz o design com template B\"_ — pula para etapa 6",
        parse_mode="Markdown"
    )


# ── CALLBACK PARA BASE ────────────────────────────────────────────────────────

async def handle_callback_base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extensão do handle_callback para gestão da base."""
    query = update.callback_query
    if query.message.chat.id != TELEGRAM_CHAT_ID:
        return
    await query.answer()
    bot  = context.bot
    data = query.data

    if data == "base_add":
        await msg(bot, "➕ Digite o @handle do perfil para adicionar:")
        _estado["aguardando_input"] = "base_adicionar"
    elif data == "base_remove":
        await msg(bot, "➖ Digite o @handle do perfil para remover:")
        _estado["aguardando_input"] = "base_remover"


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    carregar_perfil()

    async def post_init(app: Application):
        await app.bot.set_my_commands([
            BotCommand("rodar",    "Iniciar pipeline completo"),
            BotCommand("status",   "Ver status atual"),
            BotCommand("base",     "Gerenciar base de perfis"),
            BotCommand("cancelar", "Cancelar pipeline"),
            BotCommand("ajuda",    "Ver todos os comandos"),
        ])
        agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                f"*Wavy Content Bot online!* 🌊\n\n"
                f"_{agora}_\n\n"
                f"/rodar para iniciar o pipeline\n"
                f"/ajuda para ver todos os comandos"
            ),
            parse_mode="Markdown"
        )
        log.info("Wavy Pipeline Master online.")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Comandos
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("rodar",    cmd_rodar))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("base",     cmd_base))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))
    app.add_handler(CommandHandler("ajuda",    cmd_ajuda))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback_base, pattern="^base_"))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Mensagens de texto (inputs do usuário)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))

    log.info("Iniciando bot com polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
