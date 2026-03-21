"""
AGENTE 5 — DESIGNER AGENT v3
Recebe copy aprovada + imagens aprovadas.
Monta slides em HTML/CSS (Templates A / B / C),
renderiza via Playwright em PNG 1080x1350
e entrega via Telegram — slide a slide para aprovação + álbum final.
"""

import os
import json
import base64
import asyncio
import requests
from pathlib import Path
from playwright.async_api import async_playwright
from telegram import Bot, InputMediaPhoto

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

PROFILE_IMAGE_FALLBACK = "https://i.ibb.co/bMtB5PZL/488223687-8876273612474124-8754739128155263998-n.jpg"


# ── UTILS ────────────────────────────────────────────────────────────────────

def url_para_base64(url: str) -> str:
    """Baixa imagem de URL e converte para base64."""
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        ext = "jpeg"
        ct = resp.headers.get("content-type", "")
        if "png" in ct:
            ext = "png"
        elif "webp" in ct:
            ext = "webp"
        b64 = base64.b64encode(resp.content).decode()
        return f"data:image/{ext};base64,{b64}"
    except Exception as e:
        print(f"[DESIGNER] Erro ao baixar imagem: {e}")
        return ""


def baixar_imagem_perfil(profile_url: str) -> str:
    """Baixa foto de perfil, salva em /tmp/profile_image.jpg e retorna base64."""
    path = "/tmp/profile_image.jpg"
    if not os.path.exists(path):
        try:
            resp = requests.get(profile_url, timeout=15)
            with open(path, "wb") as f:
                f.write(resp.content)
        except Exception:
            return ""
    try:
        with open(path, "rb") as f:
            return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
    except Exception:
        return ""


def determinar_formato_slide(slide: dict, total_slides: int) -> str:
    """Determina o formato visual do slide baseado no tipo e posição."""
    tipo = slide.get("tipo_slide", "conteudo")
    num = slide.get("numero", 1)
    if num == 1 or tipo == "cover":
        return "cover"
    if num == total_slides or tipo == "cta":
        return "cta"
    if tipo == "dado":
        return "text_only"
    if tipo == "virada":
        return "dark"
    return "light"


# ── TEMPLATE A — DARK CINEMATOGRÁFICO ────────────────────────────────────────

def build_slide_html_a(slide_num: int, titulo: str, corpo: str,
                       img_src: str = "", profile_src: str = "",
                       formato: str = "light", total: int = 10,
                       profile: dict = None) -> str:
    nome = (profile or {}).get("nome", "wavy")
    handle = (profile or {}).get("handle", "@wavy.mkt")
    profile_src = profile_src or PROFILE_IMAGE_FALLBACK

    if formato == "cover":
        bg_style = f"background-image:url('{img_src}'); background-size:cover; background-position:center;" if img_src else "background:#111;"
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; font-family:'Montserrat',sans-serif; position:relative; }}
.bg {{ position:absolute; inset:0; {bg_style} }}
.gradient {{ position:absolute; inset:0; background:linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.75) 70%, rgba(0,0,0,0.95) 100%); }}
.copyright {{ position:absolute; top:36px; right:60px; font-size:20px; color:rgba(255,255,255,0.5); text-align:right; line-height:1.4; z-index:5; }}
.profile-row {{ position:absolute; left:50%; transform:translateX(-50%); bottom:340px; display:flex; align-items:center; gap:18px; z-index:5; }}
.avatar-wrap {{ position:relative; width:80px; height:80px; }}
.avatar-ring {{ position:absolute; inset:0; border-radius:50%; background:conic-gradient(#FF6B35,#FF3366,#9B59B6,#FF6B35); }}
.avatar-img {{ position:absolute; inset:4px; border-radius:50%; background:url('{profile_src}') center/cover, #111; border:3px solid #0a0a0a; }}
.profile-info {{ display:flex; flex-direction:column; }}
.profile-name {{ font-size:26px; font-weight:700; color:#fff; display:flex; align-items:center; gap:8px; }}
.verified {{ display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:#1DA1F2; color:#fff; font-size:14px; }}
.profile-handle {{ font-size:22px; color:rgba(255,255,255,0.7); }}
.headline {{ position:absolute; bottom:100px; left:60px; right:60px; font-size:78px; font-weight:800; line-height:1.05; letter-spacing:-0.03em; color:#fff; text-align:center; z-index:5; }}
.swipe {{ position:absolute; bottom:48px; left:50%; transform:translateX(-50%); font-size:22px; font-weight:600; color:rgba(255,255,255,0.5); z-index:5; white-space:nowrap; }}
</style></head><body>
<div class="bg"></div>
<div class="gradient"></div>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="profile-row">
  <div class="avatar-wrap"><div class="avatar-ring"></div><div class="avatar-img"></div></div>
  <div class="profile-info">
    <div class="profile-name">{nome.upper()} <span class="verified">&#10003;</span></div>
    <div class="profile-handle">{handle}</div>
  </div>
</div>
<div class="headline">{titulo}</div>
<div class="swipe">Arrasta para o lado &gt;</div>
</body></html>"""

    footer_pills = f"""<div class="footer-c">
  <div class="footer-left"><div class="pill pill-wavy">{nome.upper()}</div><div class="pill pill-handle">{handle}</div></div>
  {"<div class='footer-right'>Arrasta para o lado &gt;</div>" if slide_num < total else ""}
</div>"""

    base_css = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#0a0a0a; font-family:'Montserrat',sans-serif; position:relative; }}
.copyright {{ position:absolute; top:36px; right:60px; font-size:20px; color:#444; text-align:right; line-height:1.4; }}
.footer-c {{ position:absolute; bottom:40px; left:60px; right:60px; display:flex; align-items:center; justify-content:space-between; }}
.footer-left {{ display:flex; gap:16px; align-items:center; }}
.pill {{ padding:14px 28px; border-radius:50px; font-size:22px; font-weight:700; }}
.pill-wavy {{ background:linear-gradient(135deg,#FF6B35,#FF3366); color:#fff; }}
.pill-handle {{ background:#222; color:#fff; border:1px solid #333; }}
.footer-right {{ font-size:22px; color:#444; }}
.img-card {{ width:100%; border-radius:20px; overflow:hidden; background:#111 center/cover; flex-shrink:0; }}
.slide-title {{ font-size:72px; font-weight:800; line-height:1.1; letter-spacing:-0.03em; color:#fff; }}
.slide-body {{ font-size:40px; font-weight:400; line-height:1.4; color:#aaa; }}"""

    if formato in ["light", "conteudo"]:
        img_html = f'<div class="img-card" style="height:440px;background-image:url(\'{img_src}\');background-size:cover;background-position:center;"></div>' if img_src else ""
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:100px; bottom:120px; display:flex; flex-direction:column; gap:32px; }}
</style></head><body>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="main">
  <div class="slide-title">{titulo}</div>
  {"" if not corpo else f'<div class="slide-body">{corpo}</div>'}
  {img_html}
</div>
{footer_pills}
</body></html>"""

    elif formato == "text_only":
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:50%; transform:translateY(-50%); display:flex; flex-direction:column; gap:40px; }}
</style></head><body>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="main"><div class="slide-title">{titulo}</div><div class="slide-body">{corpo}</div></div>
{footer_pills}
</body></html>"""

    elif formato == "dark":
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:50%; transform:translateY(-50%); display:flex; flex-direction:column; gap:40px; }}
.slide-title {{ color:#fff !important; font-size:80px !important; }}
.slide-body {{ color:#777 !important; }}
</style></head><body>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="main"><div class="slide-title">{titulo}</div><div class="slide-body">{corpo}</div></div>
{footer_pills}
</body></html>"""

    elif formato == "cta":
        img_html = f'<div style="width:100%;height:460px;background:url(\'{img_src}\') center/cover;"></div>' if img_src else '<div style="width:100%;height:460px;background:#111;"></div>'
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; font-family:'Montserrat',sans-serif; background:#0a0a0a; position:relative; }}
.top-banner {{ width:100%; padding:32px 60px; background:#FFE5E8; display:flex; align-items:center; gap:20px; }}
.banner-icon {{ width:56px; height:56px; border-radius:12px; background:linear-gradient(135deg,#FF3366,#FF6B35); display:flex; align-items:center; justify-content:center; font-size:28px; color:#fff; flex-shrink:0; }}
.banner-text {{ font-size:32px; font-weight:700; color:#FF3366; }}
.bottom-content {{ position:absolute; bottom:0; left:0; right:0; padding:48px 60px; display:flex; flex-direction:column; gap:24px; }}
.profile-row {{ display:flex; align-items:center; gap:18px; }}
.avatar-wrap {{ position:relative; width:72px; height:72px; }}
.avatar-ring {{ position:absolute; inset:0; border-radius:50%; background:conic-gradient(#FF6B35,#FF3366,#9B59B6,#FF6B35); }}
.avatar-img {{ position:absolute; inset:4px; border-radius:50%; background:url('{profile_src}') center/cover, #111; border:3px solid #0a0a0a; }}
.profile-name {{ font-size:26px; font-weight:700; color:#fff; }}
.profile-handle {{ font-size:22px; color:#888; }}
.cta-text {{ font-size:64px; font-weight:800; line-height:1.1; letter-spacing:-0.03em; color:#fff; }}
</style></head><body>
<div class="top-banner"><div class="banner-icon">★</div><div class="banner-text">Segue para mais conteúdo!</div></div>
{img_html}
<div class="bottom-content">
  <div class="profile-row">
    <div class="avatar-wrap"><div class="avatar-ring"></div><div class="avatar-img"></div></div>
    <div><div class="profile-name">{nome}</div><div class="profile-handle">{handle}</div></div>
  </div>
  <div class="cta-text">{titulo}</div>
</div>
</body></html>"""

    return ""


# ── TEMPLATE B — LIGHT / TWITTER STYLE ───────────────────────────────────────

def build_slide_html_b(slide_num: int, titulo: str, corpo: str,
                       img_src: str = "", profile_src: str = "",
                       formato: str = "light", total: int = 10,
                       profile: dict = None) -> str:
    nome = (profile or {}).get("nome", "WAVY")
    handle = (profile or {}).get("handle", "@wavy.mkt")
    profile_src = profile_src or PROFILE_IMAGE_FALLBACK

    header_html = f"""
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="profile-row">
  <div class="avatar-wrap"><div class="avatar-ring"></div><div class="avatar-img"></div></div>
  <div class="profile-info">
    <div class="profile-name">{nome.upper()} <span class="verified">&#10003;</span></div>
    <div class="profile-handle">{handle}</div>
  </div>
</div>"""

    footer_html = f"""<div class="footer">
  <div class="footer-left"><div class="pill pill-wavy">{nome.upper()}</div><div class="pill pill-handle">{handle}</div></div>
  <div class="footer-right">{"Arrasta para o lado &gt;" if slide_num < total else ""}</div>
</div>"""

    base_css = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#EBEBEB; font-family:'Montserrat', sans-serif; position:relative; }}
.copyright {{ position:absolute; top:40px; right:60px; font-size:22px; font-weight:400; color:#AAAAAA; text-align:right; line-height:1.4; }}
.profile-row {{ position:absolute; top:100px; left:60px; display:flex; align-items:center; gap:22px; }}
.avatar-wrap {{ position:relative; width:90px; height:90px; }}
.avatar-ring {{ position:absolute; inset:0; border-radius:50%; background: conic-gradient(#FF6B35, #FF3366, #9B59B6, #FF6B35); padding:3px; }}
.avatar-img {{ position:absolute; inset:4px; border-radius:50%; background: url('{profile_src}') center/cover, #111; border:3px solid #EBEBEB; }}
.profile-info {{ display:flex; flex-direction:column; gap:2px; }}
.profile-name {{ font-size:28px; font-weight:700; color:#1a2332; display:flex; align-items:center; gap:8px; }}
.verified {{ display:inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:50%; background:#1DA1F2; color:#fff; font-size:16px; }}
.profile-handle {{ font-size:24px; font-weight:400; color:#5a6a7a; }}
.footer {{ position:absolute; bottom:40px; left:60px; right:60px; display:flex; align-items:center; justify-content:space-between; }}
.footer-left {{ display:flex; gap:16px; align-items:center; }}
.pill {{ padding:14px 28px; border-radius:50px; font-size:22px; font-weight:700; letter-spacing:0.02em; }}
.pill-wavy {{ background: linear-gradient(135deg, #FF6B35, #FF3366); color:#fff; }}
.pill-handle {{ background:#2d3748; color:#fff; }}
.footer-right {{ font-size:22px; font-weight:400; color:#8899AA; }}
.img-card {{ width:100%; border-radius:24px; overflow:hidden; box-shadow: 0 8px 40px rgba(0,0,0,0.12); background:#ddd center/cover; flex-shrink:0; }}"""

    if formato == "cover":
        img_html = f'<div class="img-card" style="height:540px;background-image:url(\'{img_src}\');background-size:cover;background-position:center;"></div>' if img_src else ""
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:230px; bottom:120px; display:flex; flex-direction:column; gap:36px; }}
.slide-title {{ font-size:58px; font-weight:800; line-height:1.15; letter-spacing:-0.02em; color:#1a2332; }}
</style></head><body>
{header_html}
<div class="main"><div class="slide-title">{titulo}</div>{img_html}</div>
{footer_html}
</body></html>"""

    elif formato in ["light", "conteudo", "cta"]:
        img_url_style = f"background-image:url('{img_src}');" if img_src else ""
        img_html = f'<div class="img-card" style="height:420px;{img_url_style}background-size:cover;background-position:center;"></div>' if img_src else ""
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:230px; bottom:120px; display:flex; flex-direction:column; gap:32px; }}
.slide-title {{ font-size:52px; font-weight:800; line-height:1.15; letter-spacing:-0.02em; color:#1a2332; }}
.slide-body {{ font-size:38px; font-weight:400; line-height:1.45; color:#3d4f63; }}
</style></head><body>
{header_html}
<div class="main">
  <div class="slide-title">{titulo}</div>
  {"" if not corpo else f'<div class="slide-body">{corpo}</div>'}
  {img_html}
</div>
{footer_html}
</body></html>"""

    elif formato == "text_only":
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:50%; transform:translateY(-50%); display:flex; flex-direction:column; gap:32px; }}
.slide-title {{ font-size:56px; font-weight:800; line-height:1.15; letter-spacing:-0.02em; color:#1a2332; }}
.slide-body {{ font-size:38px; font-weight:400; line-height:1.45; color:#3d4f63; }}
</style></head><body>
{header_html}
<div class="main"><div class="slide-title">{titulo}</div><div class="slide-body">{corpo}</div></div>
{footer_html}
</body></html>"""

    elif formato == "dark":
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
body {{ background:#1a2332 !important; }}
.copyright {{ color:#556677 !important; }}
.profile-name {{ color:#F0F4F8 !important; }}
.profile-handle {{ color:#7890A0 !important; }}
.avatar-img {{ border-color:#1a2332 !important; }}
.footer-right {{ color:#556677 !important; }}
.main {{ position:absolute; left:60px; right:60px; top:50%; transform:translateY(-50%); display:flex; flex-direction:column; gap:32px; }}
.slide-title {{ font-size:56px; font-weight:800; line-height:1.15; letter-spacing:-0.02em; color:#F0F4F8; }}
.slide-body {{ font-size:38px; font-weight:400; line-height:1.45; color:#A0B4C0; }}
</style></head><body>
{header_html}
<div class="main"><div class="slide-title">{titulo}</div><div class="slide-body">{corpo}</div></div>
{footer_html}
</body></html>"""

    return ""


# ── TEMPLATE C — EDITORIAL ESCURO ────────────────────────────────────────────

def build_slide_html_c(slide_num: int, titulo: str, corpo: str,
                       img_src: str = "", profile_src: str = "",
                       formato: str = "light", total: int = 10,
                       profile: dict = None) -> str:
    nome = (profile or {}).get("nome", "wavy")
    handle = (profile or {}).get("handle", "@wavy.mkt")
    profile_src = profile_src or PROFILE_IMAGE_FALLBACK

    footer_html = f"""<div class="footer-c">
  <div class="footer-left"><div class="pill pill-wavy">{nome.upper()}</div><div class="pill pill-handle">{handle}</div></div>
  {"<div class='footer-right'>Arrasta para o lado &gt;</div>" if slide_num < total else ""}
</div>"""

    base_css = f"""
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#0a0a0a; font-family:'Montserrat', sans-serif; position:relative; }}
.copyright {{ position:absolute; top:36px; right:60px; font-size:20px; color:#444; text-align:right; line-height:1.4; }}
.footer-c {{ position:absolute; bottom:40px; left:60px; right:60px; display:flex; align-items:center; justify-content:space-between; }}
.footer-left {{ display:flex; gap:16px; align-items:center; }}
.pill {{ padding:14px 28px; border-radius:50px; font-size:22px; font-weight:700; }}
.pill-wavy {{ background:linear-gradient(135deg,#FF6B35,#FF3366); color:#fff; }}
.pill-handle {{ background:#222; color:#fff; border:1px solid #333; }}
.footer-right {{ font-size:22px; color:#444; }}
.img-card {{ width:100%; border-radius:20px; overflow:hidden; background:#111 center/cover; flex-shrink:0; }}
.slide-title {{ font-size:72px; font-weight:800; line-height:1.1; letter-spacing:-0.03em; color:#fff; }}
.slide-body {{ font-size:40px; font-weight:400; line-height:1.4; color:#aaa; }}"""

    if formato == "cover":
        bg_style = f"background-image:url('{img_src}'); background-size:cover; background-position:center;" if img_src else "background:#111;"
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; font-family:'Montserrat',sans-serif; position:relative; }}
.bg {{ position:absolute; inset:0; {bg_style} }}
.gradient {{ position:absolute; inset:0; background:linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.75) 70%, rgba(0,0,0,0.95) 100%); }}
.copyright {{ position:absolute; top:36px; right:60px; font-size:20px; color:rgba(255,255,255,0.5); text-align:right; line-height:1.4; z-index:5; }}
.profile-row {{ position:absolute; left:50%; transform:translateX(-50%); bottom:340px; display:flex; align-items:center; gap:18px; z-index:5; }}
.avatar-wrap {{ position:relative; width:80px; height:80px; }}
.avatar-ring {{ position:absolute; inset:0; border-radius:50%; background:conic-gradient(#FF6B35,#FF3366,#9B59B6,#FF6B35); }}
.avatar-img {{ position:absolute; inset:4px; border-radius:50%; background:url('{profile_src}') center/cover, #111; border:3px solid #0a0a0a; }}
.profile-info {{ display:flex; flex-direction:column; }}
.profile-name {{ font-size:26px; font-weight:700; color:#fff; display:flex; align-items:center; gap:8px; }}
.verified {{ display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; background:#1DA1F2; color:#fff; font-size:14px; }}
.profile-handle {{ font-size:22px; color:rgba(255,255,255,0.7); }}
.headline {{ position:absolute; bottom:100px; left:60px; right:60px; font-size:78px; font-weight:800; line-height:1.05; letter-spacing:-0.03em; color:#fff; text-align:center; z-index:5; }}
.swipe {{ position:absolute; bottom:48px; left:50%; transform:translateX(-50%); font-size:22px; font-weight:600; color:rgba(255,255,255,0.5); z-index:5; white-space:nowrap; }}
</style></head><body>
<div class="bg"></div><div class="gradient"></div>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="profile-row">
  <div class="avatar-wrap"><div class="avatar-ring"></div><div class="avatar-img"></div></div>
  <div class="profile-info">
    <div class="profile-name">{nome.upper()} <span class="verified">&#10003;</span></div>
    <div class="profile-handle">{handle}</div>
  </div>
</div>
<div class="headline">{titulo}</div>
<div class="swipe">Arrasta para o lado &gt;</div>
</body></html>"""

    elif formato == "cta":
        img_html = f'<div style="width:100%;height:460px;background:url(\'{img_src}\') center/cover;"></div>' if img_src else '<div style="width:100%;height:460px;background:#111;"></div>'
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; font-family:'Montserrat',sans-serif; background:#0a0a0a; position:relative; }}
.top-banner {{ width:100%; padding:32px 60px; background:#FFE5E8; display:flex; align-items:center; gap:20px; }}
.banner-icon {{ width:56px; height:56px; border-radius:12px; background:linear-gradient(135deg,#FF3366,#FF6B35); display:flex; align-items:center; justify-content:center; font-size:28px; color:#fff; flex-shrink:0; }}
.banner-text {{ font-size:32px; font-weight:700; color:#FF3366; }}
.bottom-content {{ position:absolute; bottom:0; left:0; right:0; padding:48px 60px; display:flex; flex-direction:column; gap:24px; }}
.cta-text {{ font-size:64px; font-weight:800; line-height:1.1; letter-spacing:-0.03em; color:#fff; }}
.sub {{ font-size:36px; color:#888; }}
</style></head><body>
<div class="top-banner"><div class="banner-icon">★</div><div class="banner-text">Segue para mais conteúdo!</div></div>
{img_html}
<div class="bottom-content">
  <div class="cta-text">{titulo}</div>
  <div class="sub">{corpo}</div>
</div>
</body></html>"""

    elif formato in ["light", "conteudo"]:
        img_html = f'<div class="img-card" style="height:440px;background-image:url(\'{img_src}\');background-size:cover;background-position:center;"></div>' if img_src else ""
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:100px; bottom:120px; display:flex; flex-direction:column; gap:32px; }}
</style></head><body>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="main">
  <div class="slide-title">{titulo}</div>
  {"" if not corpo else f'<div class="slide-body">{corpo}</div>'}
  {img_html}
</div>
{footer_html}
</body></html>"""

    elif formato == "text_only":
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:50%; transform:translateY(-50%); display:flex; flex-direction:column; gap:40px; }}
</style></head><body>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="main"><div class="slide-title">{titulo}</div><div class="slide-body">{corpo}</div></div>
{footer_html}
</body></html>"""

    elif formato == "dark":
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{base_css}
.main {{ position:absolute; left:60px; right:60px; top:50%; transform:translateY(-50%); display:flex; flex-direction:column; gap:40px; }}
.slide-title {{ color:#fff !important; font-size:80px !important; }}
.slide-body {{ color:#777 !important; }}
</style></head><body>
<div class="copyright">Copyright &copy;<br>2026</div>
<div class="main"><div class="slide-title">{titulo}</div><div class="slide-body">{corpo}</div></div>
{footer_html}
</body></html>"""

    return ""


# ── DISPATCHER DE TEMPLATES ──────────────────────────────────────────────────

TEMPLATE_BUILDERS = {
    "A": build_slide_html_a,
    "B": build_slide_html_b,
    "C": build_slide_html_c,
}


def build_slide_html(slide_num: int, titulo: str, corpo: str,
                     img_src: str = "", profile_src: str = "",
                     formato: str = "light", total: int = 10,
                     template: str = "A", profile: dict = None) -> str:
    builder = TEMPLATE_BUILDERS.get(template, build_slide_html_a)
    return builder(slide_num, titulo, corpo, img_src, profile_src, formato, total, profile)


# ── PLAYWRIGHT ───────────────────────────────────────────────────────────────

def garantir_playwright():
    import subprocess
    subprocess.run(["playwright", "install", "chromium"], capture_output=True)
    subprocess.run(["playwright", "install-deps", "chromium"], capture_output=True)


async def renderizar_slide(html: str, output_path: str):
    """Renderiza HTML em PNG 1080x1350 via Playwright."""
    garantir_playwright()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page(viewport={"width": 1080, "height": 1350})
        await page.set_content(html, wait_until="networkidle")
        await page.screenshot(path=output_path, full_page=False)
        await browser.close()
    print(f"[DESIGNER] PNG gerado: {output_path}")


# ── TELEGRAM ─────────────────────────────────────────────────────────────────

async def enviar_slide_telegram(bot: Bot, png_path: str, caption: str = ""):
    """Envia slide individual via Telegram para aprovação."""
    with open(png_path, "rb") as f:
        await bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=f,
            caption=caption,
            parse_mode="Markdown"
        )


async def enviar_album_telegram(bot: Bot, png_paths: list[str], legenda: str):
    """Envia todos os slides aprovados como álbum no Telegram."""
    # Telegram limita 10 por media group
    for i in range(0, len(png_paths), 10):
        batch = png_paths[i:i+10]
        media = []
        for j, path in enumerate(batch):
            cap = legenda if (i == 0 and j == 0) else ""
            media.append(InputMediaPhoto(media=open(path, "rb"), caption=cap, parse_mode="Markdown"))
        await bot.send_media_group(chat_id=TELEGRAM_CHAT_ID, media=media)
        await asyncio.sleep(1)

    # Fecha os arquivos
    for path in png_paths:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


# ── RUNNER PRINCIPAL ─────────────────────────────────────────────────────────

async def run_designer(image_payload: dict = None, template: str = "A", profile: dict = None) -> list[str]:
    """
    Monta HTML, renderiza PNGs, envia slide a slide para aprovação via Telegram
    e ao final envia álbum completo + legenda.
    """
    if image_payload is None:
        try:
            with open("/tmp/wavy_images.json", "r", encoding="utf-8") as f:
                image_payload = json.load(f)
        except Exception as e:
            print(f"[DESIGNER] Payload de imagens não encontrado: {e}")
            return []

    copy_data  = image_payload.get("copy_aprovada", {})
    imagens    = image_payload.get("imagens_aprovadas", [])
    slides     = copy_data.get("slides", [])
    legenda    = copy_data.get("legenda", "")
    tema       = copy_data.get("tema", "")
    total      = len(slides)

    bot = Bot(token=TELEGRAM_TOKEN)

    # Baixa foto de perfil
    profile_url = (profile or {}).get("foto_url", PROFILE_IMAGE_FALLBACK)
    profile_src = baixar_imagem_perfil(profile_url)

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            f"🎨 *Designer iniciado!*\n\n"
            f"📌 Tema: _{tema}_\n"
            f"🖼️ Template: {template} · {total} slides\n\n"
            f"Renderizando slide a slide..."
        ),
        parse_mode="Markdown"
    )

    # Mapa de imagens por slide_num para acesso rápido
    img_map = {img["slide_num"]: img for img in imagens}

    png_paths = []
    for slide in slides:
        num    = slide.get("numero", 1)
        titulo = slide.get("titulo", "")
        corpo  = slide.get("corpo", "")
        tipo   = slide.get("tipo_slide", "conteudo")
        fmt    = determinar_formato_slide(slide, total)

        # Obtém imagem aprovada
        img_data = img_map.get(num, {})
        img_url  = img_data.get("url", "")
        img_b64  = url_para_base64(img_url) if img_url else ""

        print(f"[DESIGNER] Montando slide {num}/{total} ({fmt}, template {template})...")

        html = build_slide_html(
            slide_num=num,
            titulo=titulo,
            corpo=corpo,
            img_src=img_b64,
            profile_src=profile_src,
            formato=fmt,
            total=total,
            template=template,
            profile=profile
        )

        png_path = f"/tmp/wavy_slide_{num:02d}.png"
        try:
            await renderizar_slide(html, png_path)
            png_paths.append(png_path)

            # Envia slide para preview
            fonte = img_data.get("fonte", "sem imagem")
            await enviar_slide_telegram(
                bot, png_path,
                caption=f"📌 Slide {num}/{total} · {tipo} · imagem: {fonte}"
            )
        except Exception as e:
            print(f"[DESIGNER] Erro no slide {num}: {e}")
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"⚠️ Erro no slide {num}: {str(e)[:100]}"
            )

    # Envia álbum final
    if png_paths:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                f"✅ *{len(png_paths)} slides renderizados!*\n"
                f"Enviando álbum final..."
            ),
            parse_mode="Markdown"
        )
        await enviar_album_telegram(bot, png_paths, legenda)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"🏁 *Pipeline completo!* {len(png_paths)} slides entregues.",
            parse_mode="Markdown"
        )

    return png_paths
