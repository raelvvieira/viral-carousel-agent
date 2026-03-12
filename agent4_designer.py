"""
AGENTE 4 — DESIGNER
Recebe a copy aprovada, gera imagens no Freepik Mystic,
monta os slides em HTML/CSS, renderiza em PNG com Playwright
e envia pro Google Drive. Notifica via Telegram com o link final.
"""

import os
import json
import asyncio
import base64
import time
import httpx
from pathlib import Path
from playwright.async_api import async_playwright
from telegram import Bot
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── CONFIGURAÇÕES ───────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN     = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID   = int(os.getenv("TELEGRAM_CHAT_ID"))
FREEPIK_API_KEY    = os.getenv("FREEPIK_API_KEY")
FREEPIK_CHARACTER_ID = os.getenv("FREEPIK_CHARACTER_ID", "")  # opcional: @rael character
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")  # JSON como string

PROFILE_IMAGE_URL = "https://i.ibb.co/bMtB5PZL/488223687-8876273612474124-8754739128155263998-n.jpg"

# ─── CONFIGURAÇÃO FREEPIK ────────────────────────────────────────
FREEPIK_CONFIG = {
    "resolution": "2k",
    "aspect_ratio": "traditional_3_4",
    "model": "fluid",
    "engine": "magnific_sharpy",
    "creative_detailing": 45,
    "filter_nsfw": True
}

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

def enrich_image_prompt(prompt: str, titulo: str = "", corpo: str = "") -> str:
    """
    Enriquece o prompt de imagem com:
    1. Pessoa icônica se a copy mencionar uma marca conhecida
    2. Estilo base cinematográfico para engajamento no Instagram
    """
    texto_completo = (prompt + " " + titulo + " " + corpo).lower()

    # Detecta marca e substitui por pessoa icônica
    person_hint = ""
    for brand, person in BRAND_ICONS.items():
        if brand in texto_completo:
            person_hint = f"{person}, "
            break

    # Monta prompt enriquecido
    enriched = (
        f"Cinematic editorial photograph, {person_hint}{prompt}, "
        f"dramatic lighting, ultra-sharp focus, professional composition, "
        f"high contrast, magazine quality, "
        f"visually striking for Instagram engagement, 4k"
    )
    return enriched


FREEPIK_BASE_PROMPT = "{description}"  # prompt já vem enriquecido via enrich_image_prompt


# ─── GERAR IMAGEM NO FREEPIK ─────────────────────────────────────

async def search_freepik_stock(query: str, slide_num: int) -> str:
    """
    Busca foto real no Freepik Stock.
    Retorna o caminho local do arquivo baixado.
    """
    print(f"   📷 Buscando foto stock: {query[:60]}...")

    headers = {"x-freepik-api-key": FREEPIK_API_KEY}

    async with httpx.AsyncClient(timeout=30) as http:
        # Busca no banco de fotos
        resp = await http.get(
            "https://api.freepik.com/v1/resources",
            headers=headers,
            params={
                "term": query,
                "filters[content_type][photo]": "1",
                "filters[orientation][portrait]": "1",
                "limit": 5,
                "order": "relevance"
            }
        )

        if resp.status_code != 200:
            print(f"   ❌ Erro Stock: {resp.status_code}")
            return None

        data  = resp.json()
        items = data.get("data", [])

        if not items:
            print(f"   ⚠️  Nenhuma foto stock encontrada para: {query}")
            return None

        # Pega a primeira foto com preview disponível
        for item in items:
            previews = item.get("image", {}).get("source", {})
            url = (
                previews.get("url") or
                item.get("previews", [{}])[0].get("url") if item.get("previews") else None
            )
            if url:
                img_resp = await http.get(url)
                path = f"/tmp/slide_{slide_num}_stock.jpg"
                with open(path, "wb") as f:
                    f.write(img_resp.content)
                print(f"   ✅ Foto stock slide {slide_num} baixada!")
                return path

    return None


def should_use_stock(prompt: str) -> bool:
    """
    Decide se usa foto real (stock) ou IA (Mystic) baseado no prompt.
    Stock: quando o tema pede pessoas reais, lugares, objetos concretos.
    Mystic: quando pede composição abstrata, futurista, cinematográfica.
    """
    stock_keywords = [
        "person", "people", "team", "crowd", "audience", "athlete",
        "entrepreneur", "businessman", "office", "meeting", "conference",
        "city", "street", "restaurant", "gym", "running", "workout",
        "phone", "laptop", "computer", "device", "product",
        "real photo", "authentic", "candid", "lifestyle"
    ]
    prompt_lower = prompt.lower()
    matches = sum(1 for kw in stock_keywords if kw in prompt_lower)
    return matches >= 2  # 2+ palavras concretas = stock


async def get_image_for_slide(prompt: str, slide_num: int) -> str:
    """
    Escolhe entre Freepik Stock e Freepik Mystic baseado no prompt.
    Fallback automático se um falhar.
    """
    use_stock = should_use_stock(prompt)

    if use_stock:
        print(f"   🔀 Slide {slide_num}: usando Stock (tema concreto)")
        path = await search_freepik_stock(prompt, slide_num)
        if path:
            return path
        print(f"   🔀 Stock falhou, tentando Mystic...")

    # Mystic (IA) como opção principal ou fallback
    print(f"   🔀 Slide {slide_num}: usando Mystic (IA)")
    return await generate_image_freepik(prompt, slide_num)


async def generate_image_freepik(prompt: str, slide_num: int, use_character: bool = False) -> str:
    """
    Gera imagem no Freepik Mystic API.
    Se use_character=True e FREEPIK_CHARACTER_ID estiver configurado, usa o character @rael.
    Retorna o caminho local do arquivo PNG baixado.
    """
    full_prompt = enrich_image_prompt(prompt) if not use_character else prompt
    print(f"   🎨 Gerando imagem slide {slide_num}: {full_prompt[:80]}...")

    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": full_prompt,
        **FREEPIK_CONFIG
    }

    # Adiciona character se for o slide 10 e o ID estiver configurado
    if use_character and FREEPIK_CHARACTER_ID:
        payload["styling"] = {
            "characters": [
                {
                    "id": FREEPIK_CHARACTER_ID,
                    "strength": 90
                }
            ]
        }
        print(f"   👤 Usando character @rael (ID: {FREEPIK_CHARACTER_ID})")

    async with httpx.AsyncClient(timeout=60) as http:
        # 1. Dispara a geração
        resp = await http.post(
            "https://api.freepik.com/v1/ai/mystic",
            headers=headers,
            json=payload
        )

        if resp.status_code != 200:
            print(f"   ❌ Erro Freepik: {resp.status_code} — {resp.text}")
            return None

        data    = resp.json()
        task_id = data.get("data", {}).get("task_id")
        print(f"   ⏳ Task ID: {task_id} — aguardando...")

        # 2. Polling até completar
        for attempt in range(30):  # max 60s
            await asyncio.sleep(3)
            status_resp = await http.get(
                f"https://api.freepik.com/v1/ai/mystic/{task_id}",
                headers=headers
            )
            status_data = status_resp.json()
            status      = status_data.get("data", {}).get("status", "")

            if status == "COMPLETED":
                images = status_data.get("data", {}).get("generated", [])
                if images:
                    image_url = images[0]
                    # 3. Baixa a imagem
                    img_resp = await http.get(image_url)
                    path     = f"/tmp/slide_{slide_num}_image.jpg"
                    with open(path, "wb") as f:
                        f.write(img_resp.content)
                    print(f"   ✅ Imagem {slide_num} gerada!")
                    return path
                break

            elif status == "FAILED":
                print(f"   ❌ Freepik falhou no slide {slide_num}")
                return None

    print(f"   ⚠️  Timeout na geração do slide {slide_num}")
    return None


async def get_image_for_cta_slide(titulo: str, corpo: str) -> str:
    """
    Gera imagem específica para o slide 10 (CTA).
    Se FREEPIK_CHARACTER_ID estiver configurado → usa o character @rael.
    Caso contrário → gera imagem profissional genérica.
    """
    if FREEPIK_CHARACTER_ID:
        print("   👤 Slide 10: usando character @rael")
        prompt = (
            f"Professional Brazilian digital marketing expert, confident pose, "
            f"modern office or studio background, warm cinematic lighting, "
            f"editorial portrait style, Instagram-ready, 4k"
        )
        return await generate_image_freepik(prompt, slide_num=10, use_character=True)
    else:
        print("   🖼️  Slide 10: character não configurado, gerando imagem genérica")
        prompt = (
            f"Confident marketing professional in modern workspace, "
            f"dramatic cinematic lighting, editorial photograph style, "
            f"high contrast, professional composition, Instagram engagement, 4k"
        )
        return await generate_image_freepik(prompt, slide_num=10, use_character=False)


# ─── TEMPLATE B — FEED CLARO ─────────────────────────────────────

def build_slide_html_b(slide_num: int, titulo: str, corpo: str,
                       image_path: str = None, formato: str = "light") -> str:
    """Template B: fundo cinza claro, perfil topo-esq, pills footer, estilo Twitter/X."""
    img_b64 = ""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    profile_b64 = ""
    if os.path.exists("/tmp/profile_image.jpg"):
        with open("/tmp/profile_image.jpg", "rb") as f:
            profile_b64 = base64.b64encode(f.read()).decode()

    img_src     = f"data:image/jpeg;base64,{img_b64}" if img_b64 else ""
    profile_src = f"data:image/jpeg;base64,{profile_b64}" if profile_b64 else PROFILE_IMAGE_URL

    has_img   = bool(img_src) and formato not in ["text_only", "dark", "cta"]
    has_corpo = bool(corpo)   and formato != "cover"

    img_html   = f'<div class="image-card" style="background-image:url(\'{img_src}\');"></div>' if has_img else ""
    corpo_html = f'<div class="slide-body">{corpo}</div>' if has_corpo else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#EBEBEB; font-family:'Montserrat',sans-serif; position:relative; }}
.copyright {{ position:absolute; top:28px; right:40px; text-align:right; font-size:14px; color:#9B9B9B; line-height:1.5; }}
.profile {{ position:absolute; top:80px; left:60px; display:flex; align-items:center; gap:16px; }}
.avatar {{ width:88px; height:88px; border-radius:50%; padding:3px;
  background:linear-gradient(135deg,#f97316,#ef4444,#a855f7,#1e1b4b); flex-shrink:0; }}
.avatar-img {{ width:100%; height:100%; border-radius:50%; background:url('{profile_src}') center/cover; }}
.brand-info {{ display:flex; flex-direction:column; gap:4px; }}
.brand-row {{ display:flex; align-items:center; gap:6px; }}
.brand-name {{ font-size:28px; font-weight:700; color:#1e2d3d; line-height:1; }}
.badge {{ display:inline-flex; align-items:center; justify-content:center;
  width:22px; height:22px; background:#1d9bf0; border-radius:50%;
  color:#fff; font-size:12px; font-weight:700; }}
.handle {{ font-size:20px; color:#6B7280; }}
.main {{ position:absolute; left:60px; right:60px; top:225px; bottom:120px;
  display:flex; flex-direction:column; justify-content:flex-start; }}
.slide-title {{ font-size:52px; font-weight:700; line-height:108%; letter-spacing:-0.02em; color:#1e2d3d; margin-bottom:16px; }}
.slide-body {{ font-size:38px; font-weight:400; line-height:140%; color:#374151; margin-bottom:32px; }}
.image-card {{ width:960px; height:490px; border-radius:20px; background:#ccc center/cover; flex-shrink:0; }}
.footer {{ position:absolute; bottom:40px; left:60px; right:60px;
  display:flex; align-items:center; justify-content:space-between; }}
.pills {{ display:flex; gap:12px; align-items:center; }}
.pill-wavy {{ background:linear-gradient(135deg,#f97316,#ef4444,#ec4899); color:#fff; font-weight:700; font-size:18px; padding:10px 28px; border-radius:50px; }}
.pill-handle {{ background:#2d3748; color:#fff; font-size:18px; padding:10px 28px; border-radius:50px; }}
.arrasta {{ font-size:16px; color:#9B9B9B; }}
</style></head><body>
<div class="copyright">Copyright ©<br>2026</div>
<div class="profile">
  <div class="avatar"><div class="avatar-img"></div></div>
  <div class="brand-info">
    <div class="brand-row">
      <span class="brand-name">WAVY</span>
      <span class="badge">&#10003;</span>
    </div>
    <span class="handle">@wavy.mkt</span>
  </div>
</div>
<div class="main">
  <div class="slide-title">{titulo}</div>
  {corpo_html}
  {img_html}
</div>
<div class="footer">
  <div class="pills">
    <span class="pill-wavy">WAVY</span>
    <span class="pill-handle">@wavy.mkt</span>
  </div>
  <span class="arrasta">Arrasta para o lado &gt;</span>
</div>
</body></html>"""


# ─── TEMPLATE C — EDITORIAL ESCURO ───────────────────────────────

def build_slide_html_c(slide_num: int, titulo: str, corpo: str,
                       image_path: str = None, formato: str = "light") -> str:
    """Template C: fundo preto, tipografia grande branca, CTA com banner rosa."""
    img_b64 = ""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    profile_b64 = ""
    if os.path.exists("/tmp/profile_image.jpg"):
        with open("/tmp/profile_image.jpg", "rb") as f:
            profile_b64 = base64.b64encode(f.read()).decode()

    img_src     = f"data:image/jpeg;base64,{img_b64}" if img_b64 else ""
    profile_src = f"data:image/jpeg;base64,{profile_b64}" if profile_b64 else PROFILE_IMAGE_URL

    # ── COVER (Slide 1) ──
    if formato == "cover":
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#000; font-family:'Montserrat',sans-serif; position:relative; }}
.bg {{ position:absolute; inset:0;
  background: linear-gradient(to bottom, rgba(0,0,0,0.05) 35%, rgba(0,0,0,0.92) 65%){f", url('{img_src}') center/cover" if img_src else ""}; }}
.copyright {{ position:absolute; top:28px; right:40px; text-align:right; font-size:14px; color:rgba(255,255,255,0.6); line-height:1.5; z-index:2; }}
.content {{ position:absolute; left:60px; right:60px; top:58%; transform:translateY(-50%);
  display:flex; flex-direction:column; align-items:center; gap:24px; z-index:2; }}
.profile-row {{ display:flex; align-items:center; gap:14px; }}
.avatar {{ width:88px; height:88px; border-radius:50%; padding:3px;
  background:linear-gradient(135deg,#6d28d9,#7c3aed,#4f46e5); flex-shrink:0; }}
.avatar-img {{ width:100%; height:100%; border-radius:50%; background:url('{profile_src}') center/cover; }}
.brand-info {{ display:flex; flex-direction:column; gap:4px; }}
.brand-row {{ display:flex; align-items:center; gap:6px; }}
.brand-name {{ font-size:26px; font-weight:700; color:#fff; line-height:1; }}
.badge {{ display:inline-flex; align-items:center; justify-content:center;
  width:20px; height:20px; background:#1d9bf0; border-radius:50%; color:#fff; font-size:11px; font-weight:700; }}
.handle {{ font-size:18px; color:rgba(255,255,255,0.75); }}
.headline {{ font-size:72px; font-weight:700; line-height:105%; letter-spacing:-0.02em;
  color:#fff; text-align:center; max-width:860px; }}
.arrasta {{ position:absolute; bottom:50px; left:50%; transform:translateX(-50%);
  font-size:18px; font-weight:600; color:#fff; white-space:nowrap; z-index:2; }}
</style></head><body>
<div class="bg"></div>
<div class="copyright">Copyright &#169;<br>2026</div>
<div class="content">
  <div class="profile-row">
    <div class="avatar"><div class="avatar-img"></div></div>
    <div class="brand-info">
      <div class="brand-row">
        <span class="brand-name">WAVY</span>
        <span class="badge">&#10003;</span>
      </div>
      <span class="handle">@wavy.mkt</span>
    </div>
  </div>
  <div class="headline">{titulo}</div>
</div>
<div class="arrasta">Arrasta para o lado &gt;</div>
</body></html>"""

    # ── CTA (Slide 10) ──
    if formato == "cta":
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#0a0a0a; font-family:'Montserrat',sans-serif; }}
.banner {{ width:1080px; height:130px; background:#FFE5E8;
  display:flex; align-items:center; gap:20px; padding:0 50px; flex-shrink:0; }}
.banner-icon {{ width:52px; height:52px; background:#E8334A; border-radius:14px;
  display:flex; align-items:center; justify-content:center; color:#fff; font-size:26px; font-weight:700; flex-shrink:0; }}
.banner-text {{ font-size:26px; font-weight:700; color:#E8334A; }}
.cover-img {{ width:1080px; height:580px; background:{f"url('{img_src}') center/cover" if img_src else "#1a1a1a"}; flex-shrink:0; }}
.text-area {{ flex:1; display:flex; flex-direction:column; justify-content:center;
  padding:50px 60px 40px; gap:20px; }}
.cta-title {{ font-size:62px; font-weight:700; line-height:108%; letter-spacing:-0.02em; color:#fff; }}
.cta-body {{ font-size:36px; font-weight:400; line-height:140%; color:#C8C8C8; }}
</style></head><body style="display:flex;flex-direction:column;">
<div class="banner">
  <div class="banner-icon">&#43;</div>
  <span class="banner-text">Me siga para mais conteudos como esse!</span>
</div>
<div class="cover-img"></div>
<div class="text-area">
  <div class="cta-title">{titulo}</div>
  {f'<div class="cta-body">{corpo}</div>' if corpo else ""}
</div>
</body></html>"""

    # ── CONTENT (slides 2–9) ──
    has_img   = bool(img_src) and formato not in ["text_only", "dark"]
    img_html  = f'<div class="image-card" style="background-image:url(\'{img_src}\');"></div>' if has_img else ""
    corpo_html = f'<div class="slide-body">{corpo}</div>' if corpo else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#0a0a0a; font-family:'Montserrat',sans-serif; position:relative; }}
.copyright {{ position:absolute; top:28px; right:40px; text-align:right; font-size:14px; color:#9B9B9B; line-height:1.5; }}
.main {{ position:absolute; left:60px; right:60px; top:110px; bottom:120px;
  display:flex; flex-direction:column; justify-content:flex-start; }}
.slide-title {{ font-size:67px; font-weight:700; line-height:105%; letter-spacing:-0.02em; color:#fff; margin-bottom:20px; }}
.slide-body {{ font-size:40px; font-weight:400; line-height:140%; color:#C8C8C8; margin-bottom:30px; }}
.image-card {{ width:960px; height:490px; border-radius:20px; background:#222 center/cover; flex-shrink:0; }}
.footer {{ position:absolute; bottom:40px; left:60px; right:60px;
  display:flex; align-items:center; justify-content:space-between; }}
.pills {{ display:flex; gap:12px; align-items:center; }}
.pill-wavy {{ background:linear-gradient(135deg,#f97316,#ef4444,#ec4899); color:#fff; font-weight:700; font-size:18px; padding:10px 28px; border-radius:50px; }}
.pill-handle {{ border:2px solid rgba(255,255,255,0.35); color:#fff; font-size:18px; padding:10px 28px; border-radius:50px; background:transparent; }}
.arrasta {{ font-size:16px; color:#9B9B9B; }}
</style></head><body>
<div class="copyright">Copyright &#169;<br>2026</div>
<div class="main">
  <div class="slide-title">{titulo}</div>
  {corpo_html}
  {img_html}
</div>
<div class="footer">
  <div class="pills">
    <span class="pill-wavy">WAVY</span>
    <span class="pill-handle">@wavy.mkt</span>
  </div>
  <span class="arrasta">Arrasta para o lado &gt;</span>
</div>
</body></html>"""


# ─── MONTAR HTML DO SLIDE ────────────────────────────────────────

def build_slide_html(slide_num: int, titulo: str, corpo: str,
                     image_path: str = None, formato: str = "light",
                     template: str = "A") -> str:
    """
    Monta o HTML de um slide individual.
    template: 'A' (Cinematico) | 'B' (Feed Claro) | 'C' (Editorial Escuro)
    formato:  'cover' | 'light' | 'text_only' | 'dark' | 'cta'
    """
    if template == "B":
        return build_slide_html_b(slide_num, titulo, corpo, image_path, formato)
    if template == "C":
        return build_slide_html_c(slide_num, titulo, corpo, image_path, formato)
    # Template A (default) — codigo original abaixo

    # Converte imagem local pra base64 pra embed no HTML
    img_b64 = ""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

    # Perfil em base64
    profile_b64 = ""
    profile_path = "/tmp/profile_image.jpg"
    if os.path.exists(profile_path):
        with open(profile_path, "rb") as f:
            profile_b64 = base64.b64encode(f.read()).decode()

    img_src     = f"data:image/jpeg;base64,{img_b64}" if img_b64 else ""
    profile_src = f"data:image/jpeg;base64,{profile_b64}" if profile_b64 else PROFILE_IMAGE_URL

    # ── COVER (Slide 1) ──
    if formato == "cover":
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#000; font-family:'Montserrat',sans-serif; }}
.bg {{ position:absolute; inset:0;
  background: linear-gradient(180deg, rgba(0,0,0,0) 53.49%, rgba(0,0,0,0.9) 75%){f", url('{img_src}') center/cover" if img_src else ""}; }}
.content {{ position:absolute; bottom:80px; left:60px; right:60px;
  display:flex; flex-direction:column; align-items:center; gap:24px; }}
.profile-row {{ display:flex; align-items:center; gap:16px; }}
.avatar {{ width:72px; height:72px; border-radius:50%; border:3px solid #1ACD8A;
  background:url('{profile_src}') center/cover; flex-shrink:0; }}
.brand {{ display:flex; flex-direction:column; }}
.brand-name {{ font-size:22px; font-weight:700; color:#fff; line-height:1.5; }}
.brand-handle {{ font-size:18px; font-weight:400; color:#dfdfdf; line-height:1.5; }}
.headline {{ font-size:67px; font-weight:700; line-height:70px;
  letter-spacing:-0.02em; color:#fff; text-align:center; max-width:891px; }}
</style></head><body>
<div class="bg"></div>
<div class="content">
  <div class="profile-row">
    <div class="avatar"></div>
    <div class="brand">
      <span class="brand-name">wavy</span>
      <span class="brand-handle">@wavy.mkt</span>
    </div>
  </div>
  <div class="headline">{titulo}</div>
</div>
</body></html>"""

    # ── LIGHT com imagem (Slides 2-7) ──
    elif formato == "light":
        img_html = f'<div class="image-card" style="background-image:url(\'{img_src}\');"></div>' if img_src else ""
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#F1F1F1; font-family:'Montserrat',sans-serif; position:relative; }}
.header {{ position:absolute; width:960px; left:60px; top:27px; height:62px;
  display:flex; align-items:center; justify-content:space-between; }}
.header span {{ font-size:18px; font-weight:600; color:#848484; letter-spacing:-0.02em; flex:1; }}
.header span:nth-child(2) {{ text-align:center; }}
.header span:nth-child(3) {{ text-align:right; }}
.main {{ position:absolute; width:960px; left:60px; top:50%; transform:translateY(-50%);
  display:flex; flex-direction:column; gap:48px; }}
.text-block {{ display:flex; flex-direction:column; gap:24px; }}
.slide-title {{ font-size:67px; font-weight:700; line-height:75px;
  letter-spacing:-0.02em; color:#37474F; }}
.slide-body {{ font-size:42px; font-weight:400; line-height:130%; color:#37474F; }}
.image-card {{ width:960px; height:420px; border-radius:35px;
  box-shadow:20px 16px 50px rgba(0,0,0,0.15); background:#ddd center/cover; flex-shrink:0; }}
.footer {{ position:absolute; width:960px; left:60px; bottom:27px; height:62px;
  display:flex; align-items:center; justify-content:space-between; }}
.footer-profile {{ display:flex; align-items:center; gap:16px; }}
.avatar {{ width:60px; height:60px; border-radius:50%; border:3px solid #1ACD8A;
  background:url('{profile_src}') center/cover; flex-shrink:0; }}
.brand {{ display:flex; flex-direction:column; }}
.brand-name {{ font-size:20px; font-weight:700; color:#8D8D8D; line-height:1.5; }}
.brand-handle {{ font-size:18px; font-weight:400; color:#8E8E8E; line-height:1.5; }}
.slide-num {{ font-size:18px; font-weight:600; color:#848484; letter-spacing:-0.02em; }}
</style></head><body>
<div class="header">
  <span></span><span>wavy</span><span>@wavy.mkt</span>
</div>
<div class="main">
  <div class="text-block">
    <div class="slide-title">{titulo}</div>
    <div class="slide-body">{corpo}</div>
  </div>
  {img_html}
</div>
<div class="footer">
  <div class="footer-profile">
    <div class="avatar"></div>
    <div class="brand">
      <span class="brand-name">wavy</span>
      <span class="brand-handle">@wavy.mkt</span>
    </div>
  </div>
  <span class="slide-num">{slide_num} / 10</span>
</div>
</body></html>"""

    # ── TEXT ONLY (Slide 8) ──
    elif formato == "text_only":
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#F1F1F1; font-family:'Montserrat',sans-serif; position:relative; }}
.header {{ position:absolute; width:960px; left:60px; top:27px; height:62px;
  display:flex; align-items:center; justify-content:space-between; }}
.header span {{ font-size:18px; font-weight:600; color:#848484; letter-spacing:-0.02em; flex:1; }}
.header span:nth-child(2) {{ text-align:center; }}
.header span:nth-child(3) {{ text-align:right; }}
.main {{ position:absolute; width:960px; left:60px; top:50%; transform:translateY(-50%);
  display:flex; flex-direction:column; gap:24px; }}
.slide-title {{ font-size:67px; font-weight:700; line-height:75px;
  letter-spacing:-0.02em; color:#37474F; }}
.slide-body {{ font-size:42px; font-weight:400; line-height:130%; color:#37474F; }}
.footer {{ position:absolute; width:960px; left:60px; bottom:27px; height:62px;
  display:flex; align-items:center; justify-content:space-between; }}
.footer-profile {{ display:flex; align-items:center; gap:16px; }}
.avatar {{ width:60px; height:60px; border-radius:50%; border:3px solid #1ACD8A;
  background:url('{profile_src}') center/cover; flex-shrink:0; }}
.brand {{ display:flex; flex-direction:column; }}
.brand-name {{ font-size:20px; font-weight:700; color:#8D8D8D; line-height:1.5; }}
.brand-handle {{ font-size:18px; font-weight:400; color:#8E8E8E; line-height:1.5; }}
.slide-num {{ font-size:18px; font-weight:600; color:#848484; }}
</style></head><body>
<div class="header">
  <span></span><span>wavy</span><span>@wavy.mkt</span>
</div>
<div class="main">
  <div class="slide-title">{titulo}</div>
  <div class="slide-body">{corpo}</div>
</div>
<div class="footer">
  <div class="footer-profile">
    <div class="avatar"></div>
    <div class="brand">
      <span class="brand-name">wavy</span>
      <span class="brand-handle">@wavy.mkt</span>
    </div>
  </div>
  <span class="slide-num">8 / 10</span>
</div>
</body></html>"""

    # ── DARK (Slide 9) ──
    elif formato == "dark":
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#101010; font-family:'Montserrat',sans-serif; position:relative; }}
.header {{ position:absolute; width:960px; left:60px; top:27px; height:62px;
  display:flex; align-items:center; justify-content:space-between; }}
.header span {{ font-size:18px; font-weight:600; color:#fff; letter-spacing:-0.02em; flex:1; }}
.header span:nth-child(2) {{ text-align:center; }}
.header span:nth-child(3) {{ text-align:right; }}
.main {{ position:absolute; width:960px; left:60px; top:50%; transform:translateY(-50%);
  display:flex; flex-direction:column; gap:40px; }}
.slide-title {{ font-size:67px; font-weight:700; line-height:75px;
  letter-spacing:-0.02em; color:#F1F1F1; }}
.slide-body {{ font-size:42px; font-weight:400; line-height:130%; color:#CBCBCB; }}
.footer {{ position:absolute; width:960px; left:60px; bottom:27px; height:62px;
  display:flex; align-items:center; justify-content:space-between; }}
.footer-profile {{ display:flex; align-items:center; gap:16px; }}
.avatar {{ width:60px; height:60px; border-radius:50%; border:3px solid #1ACD8A;
  background:url('{profile_src}') center/cover; flex-shrink:0; }}
.brand {{ display:flex; flex-direction:column; }}
.brand-name {{ font-size:20px; font-weight:700; color:#BFBFBF; line-height:1.5; }}
.brand-handle {{ font-size:18px; font-weight:400; color:#8E8E8E; line-height:1.5; }}
.slide-num {{ font-size:18px; font-weight:600; color:#BFBFBF; }}
</style></head><body>
<div class="header">
  <span></span><span style="color:#fff;">wavy</span><span style="color:#fff;">@wavy.mkt</span>
</div>
<div class="main">
  <div class="slide-title">{titulo}</div>
  <div class="slide-body">{corpo}</div>
</div>
<div class="footer">
  <div class="footer-profile">
    <div class="avatar"></div>
    <div class="brand">
      <span class="brand-name">wavy</span>
      <span class="brand-handle">@wavy.mkt</span>
    </div>
  </div>
  <span class="slide-num">9 / 10</span>
</div>
</body></html>"""

    # ── CTA FINAL (Slide 10) ──
    elif formato == "cta":
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#000; font-family:'Montserrat',sans-serif; position:relative; }}
.bg {{ position:absolute; inset:0;
  background: linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,0.9) 75%){f", url('{img_src}') center/cover" if img_src else ""}; }}
.content {{
  position:absolute;
  width:959px;
  left:calc(50% - 959px/2 + 0.5px);
  top:calc(50% - 422px/2 + 422px);
  display:flex; flex-direction:column;
  align-items:center; gap:20px; z-index:5;
}}
.profile-row {{ display:flex; flex-direction:row; justify-content:center; align-items:center; gap:16px; }}
.avatar {{ width:72px; height:72px; border-radius:50%; border:3px solid #1ACD8A;
  background:url('{profile_src}') center/cover; flex-shrink:0; }}
.brand {{ display:flex; flex-direction:column; align-items:flex-start; }}
.brand-name {{ font-size:22px; font-weight:500; color:#fff; line-height:1.5; }}
.brand-handle {{ font-size:18px; font-weight:400; color:#dfdfdf; line-height:1.5; }}
.cta-text {{ width:925px; font-size:60px; font-weight:700; line-height:110%;
  letter-spacing:-0.02em; color:#fff; text-align:center; }}
</style></head><body>
<div class="bg"></div>
<div class="content">
  <div class="profile-row">
    <div class="avatar"></div>
    <div class="brand">
      <span class="brand-name">wavy</span>
      <span class="brand-handle">@wavy.mkt</span>
    </div>
  </div>
  <div class="cta-text">{titulo}</div>
</div>
</body></html>"""


# ─── INSTALAR PLAYWRIGHT ─────────────────────────────────────────

def ensure_playwright_installed():
    import subprocess
    subprocess.run(["playwright", "install", "chromium"], capture_output=True, text=True)
    subprocess.run(["playwright", "install-deps", "chromium"], capture_output=True, text=True)
    print("   ✅ Chromium pronto!")


# ─── RENDERIZAR HTML → PNG ───────────────────────────────────────

async def render_slide_to_png(html_content: str, output_path: str):
    """Usa Playwright para renderizar o HTML em PNG 1080x1350px."""
    ensure_playwright_installed()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page(viewport={"width": 1080, "height": 1350})
        await page.set_content(html_content, wait_until="networkidle")
        await page.screenshot(path=output_path, full_page=False)
        await browser.close()
    print(f"   📸 PNG gerado: {output_path}")


# ─── UPLOAD PRO GOOGLE DRIVE ─────────────────────────────────────

def upload_to_drive(file_path: str, folder_id: str, file_name: str) -> str:
    """Faz upload de um PNG pro Google Drive e retorna o link."""
    try:
        creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", credentials=creds)

        file_metadata = {
            "name": file_name,
            "parents": [folder_id],
            "driveId": folder_id
        }
        media = MediaFileUpload(file_path, mimetype="image/png", resumable=True)

        # Tenta upload normal primeiro
        try:
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True
            ).execute()
        except Exception:
            # Fallback: upload sem parent (raiz do Drive da service account)
            file_metadata_simple = {"name": file_name}
            media2 = MediaFileUpload(file_path, mimetype="image/png", resumable=True)
            file = service.files().create(
                body=file_metadata_simple,
                media_body=media2,
                fields="id, webViewLink"
            ).execute()
            # Move para a pasta depois
            file_id = file.get("id")
            service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents="root",
                supportsAllDrives=True,
                fields="id, webViewLink"
            ).execute()

        link = file.get("webViewLink", "")
        print(f"   ☁️  Upload OK: {file_name} → {link}")
        return link

    except Exception as e:
        print(f"   ❌ Erro Drive: {e}")
        return ""


# ─── NOTIFICAR TELEGRAM ──────────────────────────────────────────

async def notify_telegram_done(folder_link: str, trend_titulo: str, slide_count: int):
    """Envia notificação final pro Telegram com link da pasta."""
    bot   = Bot(token=TELEGRAM_TOKEN)
    texto = (
        f"🎉 *Carrossel pronto!*\n\n"
        f"📌 *{trend_titulo}*\n"
        f"🖼️ {slide_count} slides gerados\n\n"
        f"📁 [Acessar no Google Drive]({folder_link})\n\n"
        f"✅ Pronto pra postar!"
    )
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=texto,
        parse_mode="Markdown",
        disable_web_page_preview=False
    )


# ─── BAIXAR IMAGEM DE PERFIL ─────────────────────────────────────

async def download_profile_image():
    """Baixa a imagem de perfil uma vez e salva localmente."""
    profile_path = "/tmp/profile_image.jpg"
    if not os.path.exists(profile_path):
        async with httpx.AsyncClient() as http:
            resp = await http.get(PROFILE_IMAGE_URL)
            with open(profile_path, "wb") as f:
                f.write(resp.content)
        print("✅ Foto de perfil baixada")


# ─── EXECUTAR AGENTE 4 ───────────────────────────────────────────

async def run_designer(copy_result: dict) -> list[str]:
    """Função principal do Agente 4."""

    trend   = copy_result.get("trend", {})
    angulo  = copy_result.get("angulo", {})
    copy    = copy_result.get("copy", {})
    formato = copy_result.get("formato", "carrossel")
    bot     = Bot(token=TELEGRAM_TOKEN)

    print("🎨 Agente 4 — Designer iniciado...")

    # Avisa que começou
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            f"🎨 *Designer iniciado!*\n\n"
            f"📌 {trend.get('titulo', '')}\n"
            f"📐 Formato: {formato.capitalize()}\n\n"
            f"⏳ Gerando imagens no Freepik..."
        ),
        parse_mode="Markdown"
    )

    await download_profile_image()

    png_paths   = []
    drive_links = []

    template = copy_result.get("template", "A")

    if formato == "carrossel":
        slides = copy.get("slides", [])
        total  = len(slides)

        for slide in slides:
            n      = slide.get("slide", 0)
            titulo = slide.get("titulo_bold", "")
            corpo  = slide.get("corpo", "")
            prompt = slide.get("prompt_imagem", "")

            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"🖼️ Gerando slide *{n}/{total}*...",
                parse_mode="Markdown"
            )

            if n == 1:
                fmt = "cover"
            elif n == 8:
                fmt = "text_only"
            elif n == 9:
                fmt = "dark"
            elif n == 10:
                fmt = "cta"
            else:
                fmt = "light"

            image_path = None

            if fmt == "cta":
                # Slide 10: usa character @rael se disponível, senão genérico
                image_path = await get_image_for_cta_slide(titulo, corpo)

            elif fmt not in ["text_only", "dark"] and prompt:
                # Slides normais: enriquece prompt e escolhe Stock vs Mystic
                enriched_prompt = enrich_image_prompt(prompt, titulo, corpo)
                image_path = await get_image_for_slide(enriched_prompt, n)

            if image_path:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"✅ Imagem slide {n} gerada!"
                )

            html     = build_slide_html(n, titulo, corpo, image_path, fmt, template=template)
            png_path = f"/tmp/wavy_slide_{n:02d}.png"
            await render_slide_to_png(html, png_path)
            png_paths.append(png_path)

        # Envia todos os slides de uma vez como álbum no Telegram
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                f"✅ *{len(png_paths)} slides gerados!*\n\n"
                f"📤 Enviando carrossel...\n"
                f"📌 _{trend.get('titulo', '')}_"
            ),
            parse_mode="Markdown"
        )

        # Envia como media group (álbum) — máx 10 por envio
        from telegram import InputMediaPhoto
        media_group = []
        for i, png_path in enumerate(png_paths):
            with open(png_path, "rb") as f:
                media_group.append(InputMediaPhoto(media=f.read()))

        await bot.send_media_group(
            chat_id=TELEGRAM_CHAT_ID,
            media=media_group
        )

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                f"🎉 *Carrossel pronto!*\n\n"
                f"📌 {trend.get('titulo', '')}\n"
                f"🖼️ {len(png_paths)} slides\n\n"
                f"_Salve as imagens acima para postar no Instagram!_"
            ),
            parse_mode="Markdown"
        )

    return png_paths


if __name__ == "__main__":
    try:
        with open("/tmp/copy_result.json", "r", encoding="utf-8") as f:
            copy_result = json.load(f)
    except FileNotFoundError:
        print("❌ Rode o agent3_copywriter.py primeiro.")
        exit(1)

    links = asyncio.run(run_designer(copy_result))
    print(f"\n✅ Designer finalizado! {len(links)} slides no Drive.")
