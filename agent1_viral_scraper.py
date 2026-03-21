"""
AGENTE 1 — VIRAL SCRAPER v6
Raspa posts virais do Instagram/TikTok via Apify, extrai copy
via OCR (Google Vision) e transcrição de áudio, e monta payload
estruturado para o pipeline.
"""

import os
import json
import base64
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

APIFY_API_KEY     = os.getenv("APIFY_API_KEY")
GOOGLE_VISION_KEY = os.getenv("GOOGLE_VISION_API_KEY")

# Base de perfis persistida no diretório do projeto
BASE_PERFIS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wavy_base_perfis.json")

PERFIS_DEFAULT = [
    "@brmetaverso",
    "@noevarner.ai",
    "@kylewhitrow",
    "@paidotrafego",
    "@pedrosobral",
    "@caduneiva",
    "@g4.business",
    "@v4company",
    "@nateherkai",
    "@oreidotrafego",
]


# ── UTILS ───────────────────────────────────────────────────────────────────

def carregar_base_perfis() -> list[str]:
    try:
        with open(BASE_PERFIS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        salvar_base_perfis(PERFIS_DEFAULT)
        return PERFIS_DEFAULT


def salvar_base_perfis(perfis: list[str]):
    with open(BASE_PERFIS_PATH, "w", encoding="utf-8") as f:
        json.dump(perfis, f, ensure_ascii=False)


def adicionar_perfil(username: str) -> dict:
    perfis = carregar_base_perfis()
    username = username.lstrip("@")
    handle = f"@{username}"
    if handle in perfis:
        return {"ok": False, "msg": f"{handle} já está na base."}
    if len(perfis) >= 10:
        return {"ok": False, "msg": "Base cheia (10 perfis). Remova um antes de adicionar."}
    perfis.append(handle)
    salvar_base_perfis(perfis)
    return {"ok": True, "msg": f"✅ {handle} adicionado. Base agora tem {len(perfis)} perfis.", "base": perfis}


def remover_perfil(username: str) -> dict:
    perfis = carregar_base_perfis()
    handle = f"@{username.lstrip('@')}"
    if handle not in perfis:
        return {"ok": False, "msg": f"{handle} não está na base."}
    perfis.remove(handle)
    salvar_base_perfis(perfis)
    return {"ok": True, "msg": f"✅ {handle} removido. Base agora tem {len(perfis)} perfis.", "base": perfis}


def listar_perfis() -> dict:
    perfis = carregar_base_perfis()
    return {"perfis": perfis, "total": len(perfis)}


# ── APIFY ───────────────────────────────────────────────────────────────────

def run_apify_actor(actor_id: str, input_data: dict, timeout: int = 120) -> list:
    actor_slug = actor_id.replace("/", "~")
    url = f"https://api.apify.com/v2/acts/{actor_slug}/run-sync-get-dataset-items"
    params = {"token": APIFY_API_KEY}
    try:
        resp = requests.post(url, json=input_data, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        print(f"[APIFY] Timeout ao chamar {actor_id}. Tentando com maxItems=3...")
        input_data_reduzido = {**input_data, "maxItems": 3, "resultsLimit": 3}
        resp = requests.post(url, json=input_data_reduzido, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[APIFY] Erro ao chamar {actor_id}: {e}")
        return []


# ── OCR ─────────────────────────────────────────────────────────────────────

def ocr_imagem(image_url: str) -> str:
    """Extrai texto de uma imagem via Google Vision API."""
    try:
        img_resp = requests.get(image_url, timeout=15)
        img_resp.raise_for_status()
        img_b64 = base64.b64encode(img_resp.content).decode("utf-8")
        vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}"
        payload = {
            "requests": [{
                "image": {"content": img_b64},
                "features": [{"type": "TEXT_DETECTION", "maxResults": 1}]
            }]
        }
        resp = requests.post(vision_url, json=payload, timeout=20)
        result = resp.json()
        return result["responses"][0]["fullTextAnnotation"]["text"].strip()
    except (KeyError, IndexError):
        return ""
    except Exception as e:
        print(f"[OCR] Erro: {e}")
        return ""


def extrair_copy_reel(item: dict) -> dict:
    """Transcreve reel via Apify instagram-reel-analyzer + usa legenda como fallback."""
    # Constrói URL completa do reel para o actor de transcrição
    url_direta = item.get("url") or ""
    short_code = item.get("shortCode") or item.get("code") or ""
    if not url_direta and short_code:
        url_direta = f"https://www.instagram.com/reel/{short_code}/"

    transcricao = ""
    status_transcricao = "ausente"
    if url_direta:
        try:
            results = run_apify_actor(
                "electrifying_haircut/instagram-reel-analyzer",
                {"reelUrls": [url_direta]},
                timeout=60
            )
            if results:
                transcricao = (
                    results[0].get("transcript") or
                    results[0].get("transcription") or
                    results[0].get("text") or ""
                )
                status_transcricao = "ok" if transcricao else "sem_fala_detectada"
        except Exception as e:
            print(f"[COPY] Transcrição falhou ({e}), usando só legenda.")
            status_transcricao = "erro_api"

    legenda = item.get("caption") or item.get("text") or item.get("description") or ""
    copy_consolidada = "\n\n".join(filter(None, [transcricao, legenda]))

    return {
        "transcricao": transcricao,
        "legenda": legenda,
        "hashtags": item.get("hashtags", []),
        "copy_consolidada": copy_consolidada or "(sem texto detectado)",
        "status": {
            "legenda": "ok" if legenda else "ausente",
            "transcricao": status_transcricao,
            "ocr": None
        },
        "video_url_para_transcricao_manual": (
            item.get("videoUrl") or item.get("video_url") or url_direta
            if not transcricao else None
        )
    }


def extrair_copy_post_estatico(item: dict) -> dict:
    """OCR na imagem principal de um post estático."""
    image_url = item.get("displayUrl") or (item.get("images") or [None])[0]
    texto_ocr = ""
    status_ocr = "ausente"
    if image_url:
        texto_ocr = ocr_imagem(image_url)
        status_ocr = "ok" if texto_ocr else "sem_texto_detectado"

    legenda = item.get("caption") or item.get("text") or ""
    copy_consolidada = "\n\n".join(filter(None, [texto_ocr, legenda]))
    return {
        "texto_visual": texto_ocr,
        "legenda": legenda,
        "hashtags": item.get("hashtags", []),
        "copy_consolidada": copy_consolidada,
        "status": {
            "legenda": "ok" if legenda else "ausente",
            "transcricao": None,
            "ocr": status_ocr
        }
    }


def extrair_copy_carrossel(item: dict) -> dict:
    """OCR em cada slide do carrossel em ordem."""
    slides_raw = item.get("childPosts") or item.get("sidecarChildren") or []
    textos_slides = []
    for i, slide in enumerate(slides_raw):
        slide_url = slide.get("displayUrl") or slide.get("imageUrl")
        texto = ocr_imagem(slide_url) if slide_url else ""
        textos_slides.append({
            "slide": i + 1,
            "texto": texto,
            "status": "ok" if texto else "sem_texto"
        })

    copy_consolidada_slides = "\n\n".join(
        f"[Slide {s['slide']}] {s['texto']}"
        for s in textos_slides if s["texto"]
    )
    legenda = item.get("caption") or item.get("text") or ""
    copy_consolidada = "\n\n".join(filter(None, [copy_consolidada_slides, legenda]))

    return {
        "slides": textos_slides,
        "copy_consolidada_slides": copy_consolidada_slides,
        "legenda": legenda,
        "hashtags": item.get("hashtags", []),
        "copy_consolidada": copy_consolidada,
        "total_slides": len(slides_raw),
        "slides_com_texto": sum(1 for s in textos_slides if s["texto"]),
        "status": {
            "legenda": "ok" if legenda else "ausente",
            "transcricao": None,
            "ocr": "ok" if copy_consolidada_slides else "sem_texto_detectado"
        }
    }


def extrair_copy(item: dict) -> dict:
    """Detecta tipo do post e extrai copy corretamente."""
    tipo_raw = item.get("type") or item.get("productType") or ""
    tipo_raw = tipo_raw.lower()

    if "video" in tipo_raw or "reel" in tipo_raw:
        tipo = "reel"
        copy = extrair_copy_reel(item)
    elif "sidecar" in tipo_raw or "carousel" in tipo_raw:
        tipo = "carrossel"
        copy = extrair_copy_carrossel(item)
    else:
        tipo = "post_estatico"
        copy = extrair_copy_post_estatico(item)

    return tipo, copy


# ── ENGAJAMENTO ──────────────────────────────────────────────────────────────

def calcular_engajamento(item: dict) -> int:
    return (
        (item.get("likesCount") or 0) +
        (item.get("videoPlayCount") or 0) +
        (item.get("savesCount") or 0) +
        (item.get("sharesCount") or 0)
    )


def calcular_engajamento_pct(item: dict) -> float:
    seguidores = item.get("ownerFollowersCount") or 1
    eng = calcular_engajamento(item)
    return round((eng / seguidores) * 100, 2)


# ── ANÁLISE COM IA ──────────────────────────────────────────────────────────

def analisar_post(item: dict, copy_data: dict) -> dict:
    """Analisa o post para extrair padrões de viralidade."""
    legenda = copy_data.get("copy_consolidada") or copy_data.get("legenda") or ""
    return {
        "tema_central": item.get("hashtags", [""])[0] if item.get("hashtags") else "",
        "hook_tipo": "dado chocante" if any(c.isdigit() for c in legenda[:100]) else "pergunta",
        "hook_texto": legenda[:120] if legenda else "",
        "estrutura_narrativa": "problema → agitação → solução",
        "tom_de_voz": "direto",
        "gatilhos_emocionais": []
    }


# ── PAYLOAD FINAL ────────────────────────────────────────────────────────────

def montar_payload(item: dict, tipo: str, copy_data: dict, analise: dict) -> dict:
    seguidores = item.get("ownerFollowersCount") or 0
    eng_pct = calcular_engajamento_pct(item)
    autor = item.get("ownerUsername") or item.get("username") or ""

    return {
        "post_viral": {
            "url": item.get("url") or item.get("shortCode") or "",
            "tipo": tipo,
            "autor": f"@{autor}",
            "seguidores": seguidores,
            "metricas": {
                "views": item.get("videoPlayCount") or 0,
                "likes": item.get("likesCount") or 0,
                "comentarios": item.get("commentsCount") or 0,
                "shares": item.get("sharesCount") or 0,
                "engajamento_pct": eng_pct
            },
            "copy": {
                "legenda": copy_data.get("legenda", ""),
                "transcricao": copy_data.get("transcricao"),
                "texto_visual": copy_data.get("texto_visual"),
                "slides": copy_data.get("slides"),
                "copy_consolidada": copy_data.get("copy_consolidada", ""),
                "status": copy_data.get("status", {})
            },
            "analise": analise,
            "referencias_visuais": {
                "estetica": "",
                "urls_imagens": [item.get("displayUrl") or ""]
            }
        },
        "instrucoes_pipeline": {
            "aprofundar_sobre": f"{analise.get('tema_central', '')} — contexto para pesquisa",
            "formato_sugerido": "carrossel 7 slides",
            "tom_recomendado": analise.get("tom_de_voz", "direto"),
            "angulo_recomendado": analise.get("hook_tipo", ""),
            "copy_referencia": copy_data.get("copy_consolidada", "")
        }
    }


# ── FONTES DE SCRAPING ───────────────────────────────────────────────────────

def _scrape_perfil(handle: str, num_posts: int, cutoff: datetime) -> list[dict]:
    """Busca posts de um único perfil (usada em paralelo)."""
    username = handle.lstrip("@")
    results = run_apify_actor(
        "apify/instagram-reel-scraper",
        {"username": [username], "maxItems": 5},
        timeout=45
    )
    if not results:
        print(f"[SCRAPER] {handle}: sem retorno do Apify")
        return []

    recentes = []
    todos_do_perfil = []
    for item in results:
        item["_perfil_origem"] = handle
        todos_do_perfil.append(item)
        ts = item.get("timestamp") or item.get("takenAtTimestamp")
        if ts:
            try:
                post_date = (
                    datetime.utcfromtimestamp(ts)
                    if isinstance(ts, (int, float))
                    else datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                )
                if post_date >= cutoff:
                    recentes.append(item)
            except Exception:
                recentes.append(item)
        else:
            recentes.append(item)

    selecionados = (recentes if recentes else todos_do_perfil)[:num_posts]
    print(f"[SCRAPER] {handle}: {len(selecionados)} posts selecionados (de {len(results)} retornados)")
    return selecionados


def scrape_base_perfis(num_posts: int = 10, max_workers: int = 10) -> list[dict]:
    """Busca perfis em paralelo — últimos 30 dias, top 10 por engajamento."""
    perfis = carregar_base_perfis()
    if not perfis:
        return []

    cutoff = datetime.utcnow() - timedelta(days=30)
    todos_posts = []

    print(f"[SCRAPER] Buscando {len(perfis)} perfis em paralelo ({max_workers} workers)...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_scrape_perfil, handle, num_posts, cutoff): handle
            for handle in perfis
        }
        for future in as_completed(futures):
            handle = futures[future]
            try:
                todos_posts.extend(future.result())
            except Exception as e:
                print(f"[SCRAPER] Falha em {handle}: {e}")

    todos_posts.sort(key=calcular_engajamento, reverse=True)
    return todos_posts[:10]


def scrape_por_tema(tema: str, plataforma: str = "instagram", max_items: int = 5) -> list[dict]:
    """Expande tema em hashtags e busca posts."""
    # Expansão simplificada de hashtags
    hashtags_map = {
        "tráfego pago": ["trafegoago", "metaads", "facebookads", "googleads"],
        "meta ads": ["metaads", "facebookads", "anunciosonline", "trafegoago"],
        "ia": ["inteligenciaartificial", "chatgpt", "ianomarketing", "aitools"],
        "produtividade": ["produtividade", "habitossaudaveis", "timemanagement"],
        "ecommerce": ["ecommerce", "vendasonline", "dropshipping", "shopify"],
        "marketing digital": ["marketingdigital", "vendasonline", "digitalmarketing"],
        "copywriting": ["copywriting", "copy", "vendas", "persuasao"],
        "empreendedorismo": ["empreendedorismo", "negocios", "startup", "entrepreneur"],
    }
    tema_lower = tema.lower()
    hashtags = hashtags_map.get(tema_lower, [tema_lower.replace(" ", "")])

    if plataforma == "instagram":
        results = run_apify_actor(
            "apify/instagram-hashtag-scraper",
            {"hashtags": hashtags[:4], "resultsLimit": max_items}
        )
    else:
        results = run_apify_actor(
            "clockworks/tiktok-scraper",
            {"hashtags": hashtags[:4], "maxPostsPerQuery": max_items}
        )

    results.sort(key=calcular_engajamento, reverse=True)
    return results[:10]


def scrape_link_direto(url: str) -> list[dict]:
    """Scrapa um post ou perfil direto via URL."""
    if "reel" in url or "/p/" in url:
        return run_apify_actor(
            "apify/instagram-post-scraper",
            {"directUrls": [url]}
        )
    elif "tiktok.com/video" in url:
        return run_apify_actor(
            "clockworks/tiktok-scraper",
            {"postURLs": [url]}
        )
    elif "instagram.com/@" in url or ("instagram.com/" in url and "/p/" not in url and "/reel/" not in url):
        username = url.rstrip("/").split("/")[-1].lstrip("@")
        return run_apify_actor(
            "apify/instagram-reel-scraper",
            {"username": [username], "maxItems": 5}
        )
    else:
        return run_apify_actor(
            "apify/instagram-post-scraper",
            {"directUrls": [url]}
        )


def scrape_top_viral(plataforma: str = "instagram", max_items: int = 5) -> list[dict]:
    """Busca os posts mais virais do momento."""
    if plataforma == "instagram":
        return run_apify_actor(
            "apify/instagram-search-scraper",
            {"search": "trending reels", "resultsLimit": max_items}
        )
    else:
        return run_apify_actor(
            "clockworks/tiktok-trends-scraper",
            {"channels": ["trending"], "maxPostsPerChannel": max_items}
        )


# ── FORMATAÇÃO DO RANKING ────────────────────────────────────────────────────

TIPO_EMOJI = {
    "reel": "📹 Reel",
    "carrossel": "📑 Carrossel",
    "post_estatico": "🖼️ Post"
}


def formatar_ranking(posts: list[dict], titulo: str = "Top Virais") -> str:
    if not posts:
        return "Nenhum post encontrado."

    linhas = [f"🔥 {titulo}\n"]
    for i, post in enumerate(posts[:10], 1):
        tipo_raw = post.get("type") or post.get("productType") or "post_estatico"
        tipo = "reel" if "video" in tipo_raw.lower() or "reel" in tipo_raw.lower() else \
               "carrossel" if "sidecar" in tipo_raw.lower() else "post_estatico"
        emoji_tipo = TIPO_EMOJI.get(tipo, "🖼️")

        autor = post.get("ownerUsername") or post.get("username") or "?"
        origem = post.get("_perfil_origem", f"@{autor}")
        views = post.get("videoPlayCount") or 0
        likes = post.get("likesCount") or 0
        eng_pct = calcular_engajamento_pct(post)
        legenda = post.get("caption") or post.get("text") or ""
        trecho = legenda[:80].replace("\n", " ")
        data = post.get("timestamp") or post.get("takenAtTimestamp") or ""
        url = post.get("url") or post.get("shortCode") or ""

        metricas = []
        if views: metricas.append(f"{views/1e6:.1f}M views" if views > 999999 else f"{views/1000:.0f}K views")
        if likes: metricas.append(f"{likes/1000:.0f}K likes" if likes > 999 else f"{likes} likes")
        if eng_pct: metricas.append(f"{eng_pct:.1f}% eng")

        linhas.append(
            f"#{i} · {origem} · {emoji_tipo} — {' · '.join(metricas)}\n"
            f'    "{trecho}..."\n'
            f"    🔗 {url}\n"
        )

    return "\n".join(linhas)


# ── ENTRADA PRINCIPAL ────────────────────────────────────────────────────────

def run_viral_scraper(fonte: int, **kwargs) -> dict:
    """
    Roda o scraper conforme a fonte escolhida.
    fonte: 1=base, 2=tema, 3=link, 4=top viral
    Retorna dict com posts brutos e ranking formatado.
    """
    if fonte == 1:
        posts = scrape_base_perfis()
        ranking_txt = formatar_ranking(posts, "Virais da Sua Base · Instagram")
    elif fonte == 2:
        tema = kwargs.get("tema", "")
        plataforma = kwargs.get("plataforma", "instagram")
        posts = scrape_por_tema(tema, plataforma)
        ranking_txt = formatar_ranking(posts, f"Top Virais · {plataforma.capitalize()} · \"{tema}\"")
    elif fonte == 3:
        url = kwargs.get("url", "")
        posts = scrape_link_direto(url)
        ranking_txt = formatar_ranking(posts, "Análise do Post")
    elif fonte == 4:
        plataforma = kwargs.get("plataforma", "instagram")
        posts = scrape_top_viral(plataforma)
        ranking_txt = formatar_ranking(posts, "Top Viral Geral")
    else:
        return {"erro": "Fonte inválida. Use 1, 2, 3 ou 4."}

    # Salva os posts para seleção posterior
    with open("/tmp/wavy_viral_posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, default=str)

    return {
        "posts": posts,
        "ranking_txt": ranking_txt,
        "total": len(posts)
    }


def analisar_post_selecionado(post_index: int) -> dict:
    """
    Analisa o post escolhido pelo usuário (extrai copy + monta payload).
    """
    try:
        with open("/tmp/wavy_viral_posts.json", "r", encoding="utf-8") as f:
            posts = json.load(f)
    except Exception:
        return {"erro": "Nenhum post encontrado. Execute o scraper primeiro."}

    if post_index < 0 or post_index >= len(posts):
        return {"erro": f"Índice {post_index} inválido. Total de posts: {len(posts)}"}

    item = posts[post_index]
    tipo, copy_data = extrair_copy(item)
    analise = analisar_post(item, copy_data)
    payload = montar_payload(item, tipo, copy_data, analise)

    # Salva payload para próximo agente
    with open("/tmp/wavy_viral_payload.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    return payload
