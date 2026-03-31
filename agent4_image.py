"""
AGENTE 4 — IMAGE AGENT v3.1
Seleciona ou gera imagem para cada slide da copy aprovada.

Melhorias v3.1:
  - Classificação visual por tipo (pessoa, empresa, hardware, ambiente, diagrama)
  - Query cirúrgica por tipo — não concatenação de strings de copy
  - Filtro de domínio obrigatório (rejeita Shutterstock/Getty antes de aceitar qualquer URL)
  - Filtro de resolução mínima (800px)
  - Seleção do melhor resultado entre os 8 retornados (não só o primeiro)
  - Slide sem imagem é resultado válido — nunca força imagem ruim
"""

import os
import json
import re
import time
import requests

FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")
APIFY_API_KEY   = os.getenv("APIFY_API_KEY")
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY", "")

# ── DOMÍNIOS ──────────────────────────────────────────────────────────────────

# Rejeição automática — sempre têm watermark ou são stock pago
DOMINIOS_REJEITADOS = [
    "shutterstock", "gettyimages", "istockphoto", "dreamstime",
    "alamy", "depositphotos", "stock.adobe", "bigstockphoto",
    "123rf", "canstockphoto", "stockfresh", "vectorstock", "clipart"
]

# Domínios preferenciais por tipo de conteúdo
DOMINIOS_TECH = [
    "theverge.com", "techcrunch.com", "wired.com", "arstechnica.com",
    "engadget.com", "thenextweb.com", "9to5mac.com", "macrumors.com"
]
DOMINIOS_NEGOCIOS = [
    "bloomberg.com", "businessinsider.com", "fortune.com",
    "forbes.com", "wsj.com", "ft.com", "cnbc.com"
]
DOMINIOS_IMPRENSA = [
    "reuters.com", "apnews.com", "bbc.com", "g1.globo.com",
    "folha.uol.com.br", "estadao.com.br", "valor.com.br"
]
DOMINIOS_HARDWARE = [
    "nvidia.com", "intel.com", "amd.com", "apple.com", "samsung.com",
    "micron.com", "qualcomm.com", "arm.com", "tsmc.com",
    "tomshardware.com", "anandtech.com", "techpowerup.com"
]
DOMINIOS_LIFESTYLE = [
    "pexels.com", "unsplash.com"
]

TODOS_PREFERENCIAIS = (
    DOMINIOS_TECH + DOMINIOS_NEGOCIOS + DOMINIOS_IMPRENSA +
    DOMINIOS_HARDWARE + DOMINIOS_LIFESTYLE
)


# ── MAPEAMENTO DE MARCAS ──────────────────────────────────────────────────────

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
    "spacex": "Elon Musk",
    "twitter": "Elon Musk",
    "amazon": "Jeff Bezos",
    "aws": "Andy Jassy",
    "nvidia": "Jensen Huang",
    "geforce": "Jensen Huang",
    "rtx": "NVIDIA",
    "deepseek": "DeepSeek",
    "tiktok": "Shou Zi Chew",
    "linkedin": "Ryan Roslansky",
    "spotify": "Daniel Ek",
    "uber": "Dara Khosrowshahi",
    "airbnb": "Brian Chesky",
    "netflix": "Ted Sarandos",
    "nubank": "David Vélez",
    "ifood": "iFood",
    "mercado livre": "Mercado Livre",
    "mercadolivre": "Mercado Livre",
    "samsung": "Samsung",
    "intel": "Intel",
    "amd": "AMD",
    "qualcomm": "Qualcomm",
    "micron": "Micron",
    "disney": "Disney",
    "mcdonalds": "McDonald's",
    "mcdonald": "McDonald's",
    "coca-cola": "Coca-Cola",
    "coca cola": "Coca-Cola",
}
BRAND_LIST = set(BRAND_ICONS.keys())

# Hardware/produtos físicos reconhecíveis na copy
HARDWARE_KEYWORDS = [
    "gpu", "cpu", "chip", "placa de vídeo", "rtx", "rx ", "arc ",
    "gddr", "hbm", "tpu", "npu", "processador", "servidor",
    "iphone", "ipad", "macbook", "pixel ", "galaxy ", "surface",
    "headset", "óculos vr", "quest ", "vision pro",
    "data center", "supercomputador"
]

# Palavras que indicam slide de diagrama/dado técnico
DIAGRAMA_KEYWORDS = [
    "como funciona", "processo de", "passo a passo", "fluxo",
    "diagrama", "arquitetura", "pipeline", "framework",
    "funciona assim", "veja como", "entenda o"
]

FREEPIK_AI_CONFIG = {
    "resolution": "2k",
    "aspect_ratio": "traditional_3_4",
    "model": "flux-dev",
    "creative_detailing": 45,
    "num_images": 1
}


# ── CLASSIFICAÇÃO VISUAL ──────────────────────────────────────────────────────

def classificar_tipo_visual(titulo: str, corpo: str, prompt: str) -> str:
    """
    Classifica o slide em um dos 5 tipos visuais.
    Essa classificação determina a fonte e a query — não o tipo narrativo do slide.

    Tipos:
      pessoa   → figura pública nomeada ou CEO de marca conhecida
      empresa  → marca/empresa/produto de software sem hardware físico
      hardware → produto físico: GPU, chip, smartphone, servidor
      diagrama → conceito técnico, processo, fluxo — precisa de diagrama real
      ambiente → cenário, lifestyle, contexto sem entidade específica
    """
    texto = (titulo + " " + corpo + " " + prompt).lower()

    # Hardware físico tem prioridade sobre marca (ex: "RTX 5090 da NVIDIA")
    if any(kw in texto for kw in HARDWARE_KEYWORDS):
        return "hardware"

    # Diagrama/dado técnico
    if any(kw in texto for kw in DIAGRAMA_KEYWORDS):
        return "diagrama"

    # Pessoa pública — marca com nome de CEO mapeado
    for brand, person in BRAND_ICONS.items():
        match = (
            re.search(r'\b' + re.escape(brand) + r'\b', texto)
            if len(brand) <= 2
            else brand in texto
        )
        if match:
            # Se o nome da pessoa já aparece no texto → tipo pessoa
            if person.lower() in texto:
                return "pessoa"
            # Se é marca mas tem CEO mapeado → tipo empresa (foto da sede ou produto)
            return "empresa"

    # Ambiente/lifestyle — fallback
    return "ambiente"


# ── CONSTRUÇÃO DE QUERY POR TIPO ──────────────────────────────────────────────

def _extrair_entidade(titulo: str, corpo: str, prompt: str) -> tuple:
    """
    Extrai a entidade principal (marca/produto/pessoa) e o contexto do slide.
    Retorna (entidade, contexto).
    """
    texto = (titulo + " " + corpo + " " + prompt).lower()

    # Tenta achar a marca mais específica primeiro (mais longa = mais específica)
    marcas_encontradas = []
    for brand in BRAND_LIST:
        if len(brand) <= 2:
            if re.search(r'\b' + re.escape(brand) + r'\b', texto):
                marcas_encontradas.append(brand)
        else:
            if brand in texto:
                marcas_encontradas.append(brand)

    entidade = max(marcas_encontradas, key=len) if marcas_encontradas else ""
    nome_mapeado = BRAND_ICONS.get(entidade, entidade)

    # Contexto = primeiros 6 palavras do título limpo de stopwords
    stopwords = {"que", "com", "para", "uma", "um", "foi", "são", "está",
                 "mais", "como", "por", "sobre", "isso", "mas", "até"}
    palavras = [w for w in titulo.split() if w.lower() not in stopwords]
    contexto = " ".join(palavras[:6])

    return nome_mapeado or entidade, contexto


def construir_query(tipo_visual: str, titulo: str, corpo: str,
                    prompt: str, tipo_slide: str) -> str:
    """
    Constrói query cirúrgica para Google Images baseada no tipo visual.
    Nunca usa a copy bruta como query — extrai a entidade e constrói
    a busca como um jornalista procuraria a foto.
    """
    entidade, contexto = _extrair_entidade(titulo, corpo, prompt)
    ano = "2025"

    if tipo_visual == "pessoa":
        pessoa = entidade
        return f'"{pessoa}" keynote OR announcement OR stage OR event {ano}'

    if tipo_visual == "empresa":
        marca = entidade
        produto_keywords = ["app", "plataforma", "serviço", "sistema", "interface",
                            "dashboard", "software", "modelo", "versão", "update"]
        if any(kw in (titulo + corpo).lower() for kw in produto_keywords):
            return f'"{marca}" app OR interface OR screenshot OR product {ano}'
        return f'"{marca}" headquarters OR campus OR office building {ano}'

    if tipo_visual == "hardware":
        palavras_titulo = titulo.split()
        produto_candidatos = []
        for i, p in enumerate(palavras_titulo):
            if any(c.isdigit() for c in p) or p.upper() == p:
                seq = " ".join(palavras_titulo[max(0, i-1):i+2]).strip()
                produto_candidatos.append(seq)
        produto = produto_candidatos[0] if produto_candidatos else entidade or contexto
        return f'"{produto}" official press photo OR "press kit" OR "product shot"'

    if tipo_visual == "diagrama":
        fonte_primaria = entidade or contexto
        return f'"{fonte_primaria}" diagram OR infographic OR slide {ano}'

    # ambiente — lifestyle específico baseado no contexto do nicho
    return f"{contexto} professional photo editorial"


# ── FILTRO DE QUALIDADE ───────────────────────────────────────────────────────

def _url_rejeitada(url: str) -> bool:
    """Retorna True se a URL vem de domínio de stock pago com watermark."""
    url_lower = url.lower()
    return any(d in url_lower for d in DOMINIOS_REJEITADOS)


def _score_url(url: str, tipo_visual: str) -> int:
    """
    Score de preferência por domínio.
    Maior = melhor. 0 = aprovado mas sem bônus de domínio preferencial.
    """
    url_lower = url.lower()
    if tipo_visual in ("pessoa", "empresa", "diagrama"):
        fontes = DOMINIOS_TECH + DOMINIOS_NEGOCIOS + DOMINIOS_IMPRENSA
    elif tipo_visual == "hardware":
        fontes = DOMINIOS_HARDWARE + DOMINIOS_TECH
    else:  # ambiente
        fontes = DOMINIOS_LIFESTYLE + DOMINIOS_TECH

    for i, dominio in enumerate(fontes):
        if dominio in url_lower:
            return len(fontes) - i  # Primeiro da lista = maior score
    return 0


def selecionar_melhor_resultado(resultados: list, tipo_visual: str, tipo_slide: str) -> str:
    """
    Filtra e seleciona o melhor resultado dos 8 retornados pelo Apify.

    Critérios em ordem:
    1. Rejeitar URLs de domínios de stock pago
    2. Rejeitar imagens abaixo de 800px
    3. Para cover: preferir portrait (h > w); para demais: indiferente
    4. Entre os aprovados: priorizar domínio editorial preferencial
    5. Se nenhum aprovado: retornar None
    """
    aprovados = []

    for item in resultados:
        url = item.get("imageUrl") or item.get("thumbnailUrl") or ""
        if not url:
            continue
        if _url_rejeitada(url):
            continue

        w = item.get("width") or 0
        h = item.get("height") or 0

        # Resolução mínima — se não veio no metadado, aceita (não sabemos)
        if w and h and min(w, h) < 800:
            continue

        score = _score_url(url, tipo_visual)

        orientacao_ok = True
        if tipo_slide == "cover" and w and h:
            orientacao_ok = h >= w  # portrait para cover

        aprovados.append({
            "url": url,
            "score": score,
            "orientacao_ok": orientacao_ok,
        })

    if not aprovados:
        return None

    # Ordena: orientação correta primeiro (para cover), depois por score de domínio
    aprovados.sort(key=lambda x: (x["orientacao_ok"], x["score"]), reverse=True)
    return aprovados[0]["url"]


# ── GOOGLE IMAGES VIA APIFY ──────────────────────────────────────────────────

def buscar_google_images(query: str, tipo_visual: str, tipo_slide: str) -> str:
    """
    Busca no Google Images via hooli/google-images-scraper.
    Solicita 8 resultados, aplica filtro de qualidade e retorna a melhor URL.
    """
    actor_url = "https://api.apify.com/v2/acts/hooli~google-images-scraper/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            actor_url,
            params={"token": APIFY_API_KEY},
            json={"queries": [query], "maxResultsPerQuery": 8},
            timeout=90
        )
        resp.raise_for_status()
        resultados = resp.json()

        url = selecionar_melhor_resultado(resultados, tipo_visual, tipo_slide)

        if url:
            print(f"[IMAGE] Google ok ({tipo_visual}): {query[:50]}")
        else:
            print(f"[IMAGE] Google sem resultado aprovado: {query[:50]}")

        return url

    except Exception as e:
        print(f"[IMAGE] Google erro ({query[:50]}): {e}")
    return None


# ── PEXELS (para tipo ambiente) ───────────────────────────────────────────────

# Biblioteca de queries de lifestyle por tema detectado no slide
LIFESTYLE_QUERIES = {
    # Tech / Gaming
    "gaming": "gaming setup RGB dark room ultrawide monitor",
    "gamer": "gaming pc build neon lights dark desk",
    "esport": "esports setup dark aesthetic multiple monitors",
    "data center": "data center server room blue light rows corridor",
    "código": "computer code screen dark room developer programming",
    "developer": "developer laptop coding dark room focused",
    # Marketing / Negócios
    "marketing digital": "minimalist home office natural light laptop workspace",
    "agência": "creative agency workspace modern open office",
    "empreendedor": "entrepreneur laptop coffee shop focused working",
    "reunião": "business meeting glass office modern architecture",
    "startup": "startup team working modern open space office",
    # Finanças / Cripto
    "trading": "stock market trading screens multiple monitors dark",
    "cripto": "cryptocurrency trading setup monitors dark room",
    "investimento": "financial charts graphs dark background professional",
    "bitcoin": "bitcoin crypto digital finance dark background",
    # IA / Tecnologia abstrata
    "inteligência artificial": "artificial intelligence technology abstract digital",
    "machine learning": "neural network visualization abstract technology",
    "automação": "automation technology digital abstract blue",
    # Geral
    "default": "professional editorial modern workspace technology"
}


def _query_lifestyle(titulo: str, corpo: str) -> str:
    """Seleciona a query de lifestyle mais específica para o conteúdo do slide."""
    texto = (titulo + " " + corpo).lower()
    for keyword, query in LIFESTYLE_QUERIES.items():
        if keyword in texto:
            return query
    return LIFESTYLE_QUERIES["default"]


def buscar_pexels(query: str) -> str:
    """Busca foto no Pexels. Retorna URL de alta resolução ou None."""
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


# ── FREEPIK IA (geração) ──────────────────────────────────────────────────────

def enriquecer_prompt_freepik(prompt: str, titulo: str = "", corpo: str = "") -> str:
    """Enriquece prompt para geração de arte criativa no Freepik IA."""
    return (
        f"Cinematic editorial photograph, {prompt}, {titulo}, "
        f"dramatic lighting, ultra-sharp focus, professional composition, "
        f"high contrast, magazine quality, visually striking for Instagram, 4k, "
        f"award-winning photography"
    )


def gerar_freepik_ia(prompt_enriquecido: str) -> str:
    """Gera imagem via Freepik IA. Retorna URL ou None."""
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


def buscar_freepik_stock(query: str) -> str:
    """Busca foto no banco de imagens do Freepik."""
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


# ── SLIDES QUE NUNCA PRECISAM DE IMAGEM ──────────────────────────────────────

SLIDES_SEM_IMAGEM = {8, 9}
TIPOS_SLIDE_SEM_IMAGEM = {"text_only", "dark"}


def slide_precisa_imagem(slide: dict, total_slides: int) -> bool:
    """Retorna False para slides que o template já renderiza sem imagem."""
    num = slide.get("numero", 0)
    tipo = slide.get("tipo_slide", "")

    if tipo in TIPOS_SLIDE_SEM_IMAGEM:
        return False

    # Em carrosséis de 9+ slides, slides 8 e 9 são sempre text_only/dark
    if total_slides >= 9 and num in SLIDES_SEM_IMAGEM:
        return False

    return True


# ── SELEÇÃO POR SLIDE ─────────────────────────────────────────────────────────

def buscar_imagem_para_slide(slide: dict, total_slides: int = 10) -> dict:
    """
    Seleciona imagem para 1 slide.

    Fluxo por tipo visual:
      pessoa   → Google (keynote/event) → Google (fallback amplo) → Freepik IA
      empresa  → Google (sede/screenshot) → Google (official photo) → Freepik IA
      hardware → Google (press kit) → Google (product photo) → sem_imagem
      diagrama → Google (diagrama fonte real) → sem_imagem
      ambiente → Pexels (lifestyle específica) → Google → Freepik IA
    """
    titulo     = slide.get("titulo", "")
    corpo      = slide.get("corpo", "")
    prompt_raw = slide.get("prompt_imagem", "")
    tipo_slide = slide.get("tipo_slide", "conteudo")
    num        = slide.get("numero", 0)

    # Slides que o template renderiza sem imagem
    if not slide_precisa_imagem(slide, total_slides):
        print(f"[IMAGE] Slide {num} ({tipo_slide}) → sem imagem (layout text_only/dark)")
        return _resultado(slide, url=None, fonte="sem_imagem", tipo_visual=None)

    # Classificar tipo visual
    tipo_visual = classificar_tipo_visual(titulo, corpo, prompt_raw)
    print(f"[IMAGE] Slide {num} ({tipo_slide}) → tipo visual: {tipo_visual}")

    # Construir query principal
    query = construir_query(tipo_visual, titulo, corpo, prompt_raw, tipo_slide)
    print(f"[IMAGE] Query: {query}")

    url, fonte = None, None

    if tipo_visual == "pessoa":
        url = buscar_google_images(query, tipo_visual, tipo_slide)
        fonte = "Google Images (editorial)"
        if not url:
            entidade, _ = _extrair_entidade(titulo, corpo, prompt_raw)
            query2 = f'"{entidade}" 2025 photo'
            url = buscar_google_images(query2, tipo_visual, tipo_slide)
            fonte = "Google Images (ampla)"
        if not url:
            prompt_enr = enriquecer_prompt_freepik(prompt_raw, titulo, corpo)
            url = gerar_freepik_ia(prompt_enr)
            fonte = "Freepik IA"

    elif tipo_visual == "empresa":
        url = buscar_google_images(query, tipo_visual, tipo_slide)
        fonte = "Google Images (editorial)"
        if not url:
            entidade, _ = _extrair_entidade(titulo, corpo, prompt_raw)
            query2 = f'"{entidade}" 2025 official photo'
            url = buscar_google_images(query2, tipo_visual, tipo_slide)
            fonte = "Google Images (ampla)"
        if not url:
            prompt_enr = enriquecer_prompt_freepik(prompt_raw, titulo, corpo)
            url = gerar_freepik_ia(prompt_enr)
            fonte = "Freepik IA"

    elif tipo_visual == "hardware":
        # Só press kit oficial — nunca foto amadora, nunca IA
        url = buscar_google_images(query, tipo_visual, tipo_slide)
        fonte = "Google Images (press kit)"
        if not url:
            entidade, _ = _extrair_entidade(titulo, corpo, prompt_raw)
            query2 = f'"{entidade}" official product photo'
            url = buscar_google_images(query2, tipo_visual, tipo_slide)
            fonte = "Google Images (product)"
        if not url:
            fonte = "sem_imagem"

    elif tipo_visual == "diagrama":
        # Só diagrama da fonte real — nunca genérico
        url = buscar_google_images(query, tipo_visual, tipo_slide)
        fonte = "Google Images (diagrama)"
        if not url:
            fonte = "sem_imagem"

    else:  # ambiente
        query_lifestyle = _query_lifestyle(titulo, corpo)
        url = buscar_pexels(query_lifestyle)
        fonte = "Pexels"
        if not url:
            url = buscar_google_images(query_lifestyle, tipo_visual, tipo_slide)
            fonte = "Google Images (lifestyle)"
        if not url:
            prompt_enr = enriquecer_prompt_freepik(prompt_raw, titulo, corpo)
            url = gerar_freepik_ia(prompt_enr)
            fonte = "Freepik IA"

    ok = bool(url)
    print(f"[IMAGE] Slide {num} → {fonte} {'✅' if ok else '❌ sem imagem'}")
    return _resultado(slide, url=url or "", fonte=fonte, tipo_visual=tipo_visual)


def _resultado(slide: dict, url: str, fonte: str, tipo_visual: str) -> dict:
    return {
        "slide_num":   slide.get("numero"),
        "tipo_slide":  slide.get("tipo_slide", ""),
        "titulo":      slide.get("titulo", ""),
        "url":         url or "",
        "fonte":       fonte,
        "tipo_visual": tipo_visual,
        "ok":          bool(url)
    }


# ── TROCA DE IMAGEM ───────────────────────────────────────────────────────────

def trocar_imagem(imagens: list, slide_num: int, novo_prompt: str = None) -> list:
    """Troca a imagem de um slide específico re-executando a busca."""
    for i, img in enumerate(imagens):
        if img["slide_num"] != slide_num:
            continue

        slide_fake = {
            "numero":        slide_num,
            "tipo_slide":    img.get("tipo_slide", "conteudo"),
            "titulo":        img.get("titulo", ""),
            "corpo":         "",
            "prompt_imagem": novo_prompt or ""
        }
        novo = buscar_imagem_para_slide(slide_fake, total_slides=10)
        imagens[i] = {**img, **novo}
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
        "copy_aprovada":       copy_data,
        "copy_completa":       copy_payload.get("copy_completa", {}),
        "resumo_pesquisa":     copy_payload.get("resumo_pesquisa", ""),
        "tema_central":        copy_payload.get("tema_central", ""),
        "post_viral":          copy_payload.get("post_viral", {}),
        "instrucoes_pipeline": copy_payload.get("instrucoes_pipeline", {})
    }

    if not slides:
        return {"imagens_aprovadas": [], "total_imagens": 0, "imagens_ok": 0, **base}

    total = len(slides)
    print(f"[IMAGE] Buscando imagens para {total} slides...")

    imagens = []
    for slide in slides:
        resultado = buscar_imagem_para_slide(slide, total_slides=total)
        imagens.append(resultado)
        time.sleep(1)  # Rate limiting entre chamadas Apify

    total_ok = sum(1 for img in imagens if img["ok"])
    print(f"[IMAGE] {total_ok}/{total} slides com imagem")

    payload = {
        "imagens_aprovadas": imagens,
        "total_imagens":     total,
        "imagens_ok":        total_ok,
        **base
    }

    with open("/tmp/wavy_images.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    return payload
