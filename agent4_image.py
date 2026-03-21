"""
AGENTE 4 — IMAGE AGENT v2
Seleciona ou gera imagem para cada slide da copy aprovada.
Fontes em ordem de prioridade:
  1. Freepik IA (geração via texto)
  2. Google Images via Apify (foto real)
  3. Bancos gratuitos: Pexels / Unsplash (fallback)
Retorna URLs aprovadas para o Designer Agent.
"""

import os
import json
import time
import requests

FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")
APIFY_API_KEY   = os.getenv("APIFY_API_KEY")
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY", "")

# Mapeamento de marcas → pessoas icônicas
BRAND_ICONS = {
    "meta": "Mark Zuckerberg",
    "facebook": "Mark Zuckerberg",
    "instagram": "Mark Zuckerberg",
    "whatsapp": "Mark Zuckerberg",
    "google": "Sundar Pichai",
    "youtube": "Sundar Pichai",
    "apple": "Tim Cook",
    "microsoft": "Satya Nadella",
    "openai": "Sam Altman",
    "chatgpt": "Sam Altman",
    "anthropic": "Dario Amodei",
    "claude": "Dario Amodei",
    "tesla": "Elon Musk",
    "x": "Elon Musk",
    "twitter": "Elon Musk",
    "spacex": "Elon Musk",
    "amazon": "Jeff Bezos",
    "nike": "Phil Knight",
    "tiktok": "Shou Zi Chew",
    "linkedin": "Ryan Roslansky",
    "spotify": "Daniel Ek",
    "uber": "Dara Khosrowshahi",
    "airbnb": "Brian Chesky",
    "netflix": "Ted Sarandos",
}

FREEPIK_CONFIG = {
    "resolution": "2k",
    "aspect_ratio": "traditional_3_4",
    "model": "flux-dev",
    "engine": "magnific_sharpy",
    "creative_detailing": 45,
    "filter_nsfw": True
}


# ── ENRIQUECIMENTO DE PROMPT ─────────────────────────────────────────────────

def enriquecer_prompt(prompt: str, titulo: str = "", corpo: str = "") -> str:
    """Enriquece prompt com estilo cinematográfico e pessoa icônica se houver marca."""
    texto = (prompt + " " + titulo + " " + corpo).lower()
    person_hint = ""
    for brand, person in BRAND_ICONS.items():
        if brand in texto:
            person_hint = f"{person}, "
            break

    return (
        f"Cinematic editorial photograph, {person_hint}{prompt}, "
        f"dramatic lighting, ultra-sharp focus, professional composition, "
        f"high contrast, magazine quality, visually striking for Instagram engagement, 4k"
    )


# ── FREEPIK IA ───────────────────────────────────────────────────────────────

def gerar_freepik(prompt_enriquecido: str) -> str | None:
    """Gera imagem via Freepik IA e retorna URL."""
    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Content-Type": "application/json"
    }

    # Enfileira geração
    payload = {
        "prompt": prompt_enriquecido,
        **{k: v for k, v in FREEPIK_CONFIG.items() if k != "filter_nsfw"},
        "num_images": 1
    }

    try:
        resp = requests.post(
            "https://api.freepik.com/v1/ai/text-to-image",
            json=payload, headers=headers, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("data", {}).get("task_id") or data.get("task_id")
        if not task_id:
            return None

        # Polling do resultado
        for _ in range(24):
            time.sleep(5)
            poll = requests.get(
                f"https://api.freepik.com/v1/ai/text-to-image/{task_id}",
                headers=headers, timeout=20
            )
            poll.raise_for_status()
            result = poll.json()
            status = result.get("data", {}).get("status") or result.get("status")
            if status == "completed":
                images = result.get("data", {}).get("images") or result.get("images", [])
                return images[0].get("url") if images else None
            if status in ("failed", "error"):
                return None

    except Exception as e:
        print(f"[IMAGE] Freepik erro: {e}")
        return None

    return None


# ── GOOGLE IMAGES VIA APIFY ──────────────────────────────────────────────────

def buscar_google_images(query: str, orientacao: str = "portrait") -> str | None:
    """Busca foto real no Google Images via Apify."""
    actor_url = "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            actor_url,
            params={"token": APIFY_API_KEY},
            json={
                "queries": f"{query} site:unsplash.com OR site:pexels.com -pinterest",
                "maxPagesPerQuery": 1,
                "resultsPerPage": 10,
                "languageCode": "pt",
                "countryCode": "br"
            },
            timeout=60
        )
        resp.raise_for_status()
        results = resp.json()
        for item in results:
            # Pega primeiro resultado que seja imagem
            if item.get("imageUrl") or item.get("thumbnailUrl"):
                return item.get("imageUrl") or item.get("thumbnailUrl")
        # Fallback: pega URL da página
        if results:
            return results[0].get("url")
    except Exception as e:
        print(f"[IMAGE] Google Images erro: {e}")
    return None


# ── PEXELS ───────────────────────────────────────────────────────────────────

def buscar_pexels(query: str) -> str | None:
    """Busca foto no Pexels (gratuito)."""
    if not PEXELS_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "orientation": "portrait", "per_page": 5},
            timeout=15
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if photos:
            return photos[0]["src"]["large2x"]
    except Exception as e:
        print(f"[IMAGE] Pexels erro: {e}")
    return None


# ── UNSPLASH ─────────────────────────────────────────────────────────────────

def buscar_unsplash(query: str) -> str | None:
    """Busca foto no Unsplash sem autenticação (URL direta)."""
    query_enc = query.replace(" ", "+")
    try:
        # Unsplash Source API — não precisa de key
        url = f"https://source.unsplash.com/1080x1350/?{query_enc}"
        resp = requests.head(url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return resp.url
    except Exception as e:
        print(f"[IMAGE] Unsplash erro: {e}")
    return None


# ── SELEÇÃO POR TIPO DE SLIDE ─────────────────────────────────────────────────

FONTE_PRIORIDADE = {
    "cover": ["freepik", "google", "unsplash"],
    "conteudo": ["freepik", "google", "pexels"],
    "dado": ["google", "unsplash", "pexels"],
    "virada": ["freepik", "google", "unsplash"],
    "cta": ["freepik", "google", "unsplash"],
    "default": ["freepik", "google", "pexels"]
}


def buscar_imagem_para_slide(slide: dict) -> dict:
    """Tenta cada fonte em ordem de prioridade e retorna a melhor URL."""
    tipo = slide.get("tipo_slide", "default")
    prompt_raw = slide.get("prompt_imagem", "")
    titulo = slide.get("titulo", "")
    corpo = slide.get("corpo", "")

    prompt_enriquecido = enriquecer_prompt(prompt_raw, titulo, corpo)
    prioridades = FONTE_PRIORIDADE.get(tipo, FONTE_PRIORIDADE["default"])

    url = None
    fonte_usada = None

    for fonte in prioridades:
        if fonte == "freepik":
            url = gerar_freepik(prompt_enriquecido)
            fonte_usada = "Freepik IA"
        elif fonte == "google":
            # Usa versão curta do prompt para Google
            query = f"{titulo} {prompt_raw}"[:80]
            url = buscar_google_images(query)
            fonte_usada = "Google Images"
        elif fonte == "pexels":
            query = f"{titulo} {prompt_raw}"[:60]
            url = buscar_pexels(query)
            fonte_usada = "Pexels"
        elif fonte == "unsplash":
            query = f"{titulo} {prompt_raw}"[:60]
            url = buscar_unsplash(query)
            fonte_usada = "Unsplash"

        if url:
            break

    return {
        "slide_num": slide.get("numero"),
        "tipo_slide": tipo,
        "titulo": titulo,
        "url": url or "",
        "fonte": fonte_usada or "não encontrada",
        "prompt_usado": prompt_enriquecido[:200],
        "ok": bool(url)
    }


# ── FORMATAÇÃO PARA APROVAÇÃO ─────────────────────────────────────────────────

def formatar_para_aprovacao(imagens: list[dict]) -> str:
    """Formata a lista de imagens para o usuário aprovar."""
    linhas = [f"🖼️ Imagens selecionadas — {len(imagens)} slides\n"]
    for img in imagens:
        status = "✅" if img["ok"] else "❌ não encontrada"
        linhas.append(
            f"Slide {img['slide_num']} ({img['tipo_slide']}) · {img['fonte']} · {status}\n"
            f"   {img['url'] or '—'}\n"
        )
    linhas.append("\n─────────────────────────")
    linhas.append("Aprovado? Ou quer trocar alguma imagem específica?")
    linhas.append('(ex: "troca a do slide 3")')
    return "\n".join(linhas)


def trocar_imagem(imagens: list[dict], slide_num: int, novo_prompt: str = None) -> list[dict]:
    """Troca a imagem de um slide específico."""
    for i, img in enumerate(imagens):
        if img["slide_num"] == slide_num:
            prompt = novo_prompt or img.get("prompt_usado", "")

            # Tenta forçar Freepik primeiro
            url = gerar_freepik(enriquecer_prompt(prompt))
            fonte = "Freepik IA"

            if not url:
                url = buscar_google_images(prompt[:80])
                fonte = "Google Images"
            if not url:
                url = buscar_unsplash(prompt[:60])
                fonte = "Unsplash"

            imagens[i] = {**img, "url": url or "", "fonte": fonte, "ok": bool(url)}
            break
    return imagens


# ── ENTRADA PRINCIPAL ────────────────────────────────────────────────────────

def run_image_agent(copy_payload: dict = None) -> dict:
    """
    Executa o image agent completo.
    Se copy_payload for None, tenta carregar de /tmp/wavy_copy.json.
    """
    if copy_payload is None:
        try:
            with open("/tmp/wavy_copy.json", "r", encoding="utf-8") as f:
                copy_payload = json.load(f)
        except Exception as e:
            return {"erro": f"Copy aprovada não encontrada: {e}"}

    copy_data = copy_payload.get("copy_aprovada", {})
    slides = copy_data.get("slides", [])

    if not slides:
        # Reel não precisa de imagens
        return {
            "imagens_aprovadas": [],
            "formato": copy_data.get("formato"),
            "copy_aprovada": copy_data,
            "briefing_pesquisa": copy_payload.get("briefing_pesquisa", {}),
            "post_viral": copy_payload.get("post_viral", {}),
            "instrucoes_pipeline": copy_payload.get("instrucoes_pipeline", {})
        }

    print(f"[IMAGE] Buscando imagens para {len(slides)} slides...")
    imagens = []
    for slide in slides:
        print(f"[IMAGE] Slide {slide.get('numero')} ({slide.get('tipo_slide')})...")
        resultado = buscar_imagem_para_slide(slide)
        imagens.append(resultado)
        time.sleep(1)  # Rate limiting

    total_ok = sum(1 for img in imagens if img["ok"])
    print(f"[IMAGE] {total_ok}/{len(slides)} imagens encontradas")

    payload = {
        "imagens_aprovadas": imagens,
        "total_imagens": len(imagens),
        "imagens_ok": total_ok,
        "aprovacao_txt": formatar_para_aprovacao(imagens),
        "copy_aprovada": copy_data,
        "briefing_pesquisa": copy_payload.get("briefing_pesquisa", {}),
        "post_viral": copy_payload.get("post_viral", {}),
        "instrucoes_pipeline": copy_payload.get("instrucoes_pipeline", {})
    }

    # Salva para o designer
    with open("/tmp/wavy_images.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    return payload
