"""
AGENTE 4 — IMAGE AGENT v3
Seleciona ou gera imagem para cada slide da copy aprovada.

Racional de fonte:
  - Marca / pessoa / empresa conhecida → Google Images (foto real)
  - Abstrato / criativo / conceitual   → Freepik IA (arte gerada) → Freepik Stock
  - Fallback final                     → Google Images

Reel não possui slides — Agent 4 é pulado no scheduler.
"""

import os
import json
import time
import requests

FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")
APIFY_API_KEY   = os.getenv("APIFY_API_KEY")

# Mapeamento de marcas → pessoas/nomes icônicos (para enriquecer query Google)
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
    "mcdonalds": "McDonald's",
    "mcdonald": "McDonald's",
    "coca-cola": "Coca-Cola",
    "coca cola": "Coca-Cola",
    "samsung": "Samsung",
    "disney": "Disney",
    "nubank": "David Vélez",
    "ifood": "iFood",
    "mercado livre": "Mercado Livre",
    "mercadolivre": "Mercado Livre",
}

BRAND_LIST = set(BRAND_ICONS.keys())

FREEPIK_AI_CONFIG = {
    "resolution": "2k",
    "aspect_ratio": "traditional_3_4",
    "model": "flux-dev",
    "creative_detailing": 45,
    "num_images": 1
}


# ── DETECÇÃO DE MARCA ─────────────────────────────────────────────────────────

def detectar_marca(titulo: str, corpo: str = "", prompt: str = "") -> tuple:
    """
    Detecta se o slide menciona uma marca ou pessoa conhecida.
    Retorna (is_brand: bool, nome_da_marca: str | None).
    """
    texto = (titulo + " " + corpo + " " + prompt).lower()
    for brand in BRAND_LIST:
        if brand in texto:
            return True, brand
    return False, None


# ── ENRIQUECIMENTO DE PROMPT PARA FREEPIK IA ─────────────────────────────────

def enriquecer_prompt_freepik(prompt: str, titulo: str = "", corpo: str = "") -> str:
    """Enriquece prompt para geração de arte criativa no Freepik IA."""
    return (
        f"Cinematic editorial photograph, {prompt}, {titulo}, "
        f"dramatic lighting, ultra-sharp focus, professional composition, "
        f"high contrast, magazine quality, visually striking for Instagram, 4k, "
        f"award-winning photography"
    )


# ── FREEPIK IA (GERAÇÃO DE ARTE) ─────────────────────────────────────────────

def gerar_freepik_ia(prompt_enriquecido: str) -> str | None:
    """Gera imagem criativa via Freepik IA (flux-dev). Retorna URL ou None."""
    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"prompt": prompt_enriquecido, **FREEPIK_AI_CONFIG}

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
        print(f"[IMAGE] Freepik IA erro: {e}")
    return None


# ── FREEPIK STOCK (BANCO DE IMAGENS) ─────────────────────────────────────────

def buscar_freepik_stock(query: str) -> str | None:
    """Busca foto no banco de imagens do Freepik. Retorna URL ou None."""
    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Accept-Language": "en-US"
    }
    params = {
        "term": query[:100],
        "page": 1,
        "limit": 5,
        "order": "relevance",
        "filters[orientation]": "portrait",
        "filters[content_type]": "photo",
    }
    try:
        resp = requests.get(
            "https://api.freepik.com/v1/resources",
            headers=headers, params=params, timeout=20
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        for item in data:
            url = item.get("image", {}).get("source", {}).get("url")
            if url:
                return url
    except Exception as e:
        print(f"[IMAGE] Freepik Stock erro: {e}")
    return None


# ── GOOGLE IMAGES VIA APIFY ──────────────────────────────────────────────────

def _gerar_queries_google(titulo: str, prompt_raw: str, marca_nome: str | None) -> list:
    """Gera até 5 variações de query para busca no Google Images."""
    queries = []
    if marca_nome:
        person = BRAND_ICONS.get(marca_nome, marca_nome)
        queries.append(f"{person} photo")
        queries.append(f"{marca_nome} brand official photo")
    queries.append(f"{titulo} {prompt_raw}"[:80])
    queries.append(f"{titulo} photography -pinterest")
    queries.append(titulo[:60])
    # Remove duplicatas mantendo ordem
    seen, dedup = set(), []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            dedup.append(q)
    return dedup[:5]


def buscar_google_images(queries: list, max_tentativas: int = 5) -> str | None:
    """
    Busca imagem no Google Images via Apify.
    Tenta cada query (até max_tentativas), para na primeira com resultado.
    """
    actor_url = "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items"
    for query in queries[:max_tentativas]:
        try:
            resp = requests.post(
                actor_url,
                params={"token": APIFY_API_KEY},
                json={
                    "queries": query,
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
                url = item.get("imageUrl") or item.get("thumbnailUrl")
                if url:
                    print(f"[IMAGE] Google ok: {query[:50]}")
                    return url
        except Exception as e:
            print(f"[IMAGE] Google erro ({query[:40]}): {e}")
    return None


# ── SELEÇÃO POR SLIDE ─────────────────────────────────────────────────────────

def buscar_imagem_para_slide(slide: dict) -> dict:
    """
    Seleciona imagem para 1 slide.
    Marca/pessoa → Google Images (foto real).
    Abstrato/criativo → Freepik IA → Freepik Stock → Google.
    """
    titulo     = slide.get("titulo", "")
    corpo      = slide.get("corpo", "")
    prompt_raw = slide.get("prompt_imagem", "")
    prompt_enriquecido = enriquecer_prompt_freepik(prompt_raw, titulo, corpo)

    is_brand, marca_nome = detectar_marca(titulo, corpo, prompt_raw)

    url, fonte = None, None

    if is_brand:
        # Marca / pessoa → foto real do Google
        queries = _gerar_queries_google(titulo, prompt_raw, marca_nome)
        url = buscar_google_images(queries)
        fonte = "Google Images"
        if not url:
            url = buscar_freepik_stock(f"{titulo} {prompt_raw}"[:80])
            fonte = "Freepik Stock"
    else:
        # Abstrato / criativo → arte gerada pelo Freepik IA
        url = gerar_freepik_ia(prompt_enriquecido)
        fonte = "Freepik IA"
        if not url:
            url = buscar_freepik_stock(f"{titulo} {prompt_raw}"[:80])
            fonte = "Freepik Stock"
        if not url:
            queries = _gerar_queries_google(titulo, prompt_raw, None)
            url = buscar_google_images(queries)
            fonte = "Google Images"

    print(f"[IMAGE] Slide {slide.get('numero')} ({slide.get('tipo_slide')}) → {fonte} {'✅' if url else '❌'}")
    return {
        "slide_num": slide.get("numero"),
        "tipo_slide": slide.get("tipo_slide", ""),
        "titulo": titulo,
        "url": url or "",
        "fonte": fonte or "não encontrada",
        "prompt_usado": prompt_enriquecido[:200],
        "is_brand": is_brand,
        "ok": bool(url)
    }


# ── TROCA DE IMAGEM (1 CHAMADA DE API) ───────────────────────────────────────

def trocar_imagem(imagens: list, slide_num: int) -> list:
    """
    Troca a imagem de um slide com UMA única chamada de API.
    Sem cascade de fallbacks — se falhar, retorna ok=False.
    O usuário pode clicar novamente para uma nova tentativa.
    """
    for i, img in enumerate(imagens):
        if img["slide_num"] != slide_num:
            continue

        is_brand = img.get("is_brand", False)
        titulo   = img.get("titulo", "")
        prompt   = img.get("prompt_usado", "")

        if not is_brand:
            is_brand, _ = detectar_marca(titulo, "", prompt)

        _, marca_nome = detectar_marca(titulo, "", prompt)

        if is_brand:
            queries = _gerar_queries_google(titulo, prompt, marca_nome)
            url = buscar_google_images(queries)
            fonte = "Google Images"
        else:
            url = gerar_freepik_ia(prompt)
            fonte = "Freepik IA"

        imagens[i] = {**img, "url": url or "", "fonte": fonte, "ok": bool(url)}
        print(f"[IMAGE] Troca slide {slide_num} → {fonte} {'✅' if url else '❌'}")
        break

    return imagens


# ── ENTRADA PRINCIPAL ────────────────────────────────────────────────────────

def run_image_agent(copy_payload: dict = None) -> dict:
    """
    Executa o image agent completo.
    Se copy_payload for None, tenta carregar de /tmp/wavy_copy.json.
    Reel (sem slides) retorna imagens_aprovadas vazio imediatamente.
    """
    if copy_payload is None:
        try:
            with open("/tmp/wavy_copy.json", "r", encoding="utf-8") as f:
                copy_payload = json.load(f)
        except Exception as e:
            return {"erro": f"Copy aprovada não encontrada: {e}"}

    copy_data = copy_payload.get("copy_aprovada", {})
    slides    = copy_data.get("slides", [])

    base = {
        "copy_aprovada": copy_data,
        "copy_completa": copy_payload.get("copy_completa", {}),
        "resumo_pesquisa": copy_payload.get("resumo_pesquisa", ""),
        "tema_central": copy_payload.get("tema_central", ""),
        "post_viral": copy_payload.get("post_viral", {}),
        "instrucoes_pipeline": copy_payload.get("instrucoes_pipeline", {})
    }

    if not slides:
        return {"imagens_aprovadas": [], "total_imagens": 0, "imagens_ok": 0, **base}

    print(f"[IMAGE] Buscando imagens para {len(slides)} slides...")
    imagens = []
    for slide in slides:
        resultado = buscar_imagem_para_slide(slide)
        imagens.append(resultado)
        time.sleep(1)

    total_ok = sum(1 for img in imagens if img["ok"])
    print(f"[IMAGE] {total_ok}/{len(slides)} imagens encontradas")

    payload = {
        "imagens_aprovadas": imagens,
        "total_imagens": len(imagens),
        "imagens_ok": total_ok,
        **base
    }

    with open("/tmp/wavy_images.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    return payload
