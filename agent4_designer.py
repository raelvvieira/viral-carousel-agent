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

FREEPIK_BASE_PROMPT = (
    "Cinematic editorial photograph, {description}, "
    "clean modern aesthetic, dramatic lighting, ultra-sharp, "
    "professional composition, futuristic minimalist background, "
    "high contrast, magazine quality, 4k"
)


# ─── GERAR IMAGEM NO FREEPIK ─────────────────────────────────────

async def generate_image_freepik(prompt: str, slide_num: int) -> str:
    """
    Gera imagem no Freepik Mystic API.
    Retorna o caminho local do arquivo PNG baixado.
    """
    full_prompt = FREEPIK_BASE_PROMPT.format(description=prompt)
    print(f"   🎨 Gerando imagem slide {slide_num}: {prompt[:60]}...")

    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": full_prompt,
        **FREEPIK_CONFIG
    }

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


# ─── MONTAR HTML DO SLIDE ────────────────────────────────────────

def build_slide_html(slide_num: int, titulo: str, corpo: str,
                     image_path: str = None, formato: str = "light") -> str:
    """
    Monta o HTML de um slide individual baseado no template Wavy.
    formato: 'cover' | 'light' | 'text_only' | 'dark' | 'cta'
    """

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
            if prompt and fmt not in ["text_only", "dark"]:
                image_path = await generate_image_freepik(prompt, n)
                if image_path:
                    await bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=f"✅ Imagem slide {n} gerada!"
                    )

            html     = build_slide_html(n, titulo, corpo, image_path, fmt)
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
