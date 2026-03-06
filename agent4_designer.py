"""
AGENTE 1 — SCOUT
Monitora tendências virais em Marketing Digital, Meta Ads, Google Ads, IA e Negócios.
Roda 3x por semana (seg/qua/sex) e retorna top 5 trends com score de viralidade.
"""

import os
import json
import asyncio
import httpx
from datetime import datetime
from anthropic import Anthropic

# ─── CONFIGURAÇÕES ───────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NOTION_TOKEN      = os.getenv("NOTION_TOKEN")
NOTION_DB_TRENDS  = os.getenv("NOTION_DB_TRENDS")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── FONTES MONITORADAS ──────────────────────────────────────────
SOURCES = [
    "https://feeds.feedburner.com/socialmediaexaminer",
    "https://blog.hootsuite.com/feed/",
    "https://searchengineland.com/feed",
    "https://www.jonloomer.com/feed/",
    "https://marketingland.com/feed",
    "https://www.reddit.com/r/PPC/top.json?limit=10&t=week",
    "https://www.reddit.com/r/FacebookAds/top.json?limit=10&t=week",
    "https://www.reddit.com/r/artificial/top.json?limit=10&t=week",
    "https://www.reddit.com/r/marketing/top.json?limit=10&t=week",
    "https://www.reddit.com/r/Entrepreneur/top.json?limit=10&t=week",
]

TOPICS = [
    "Meta Ads", "Google Ads", "Marketing Digital",
    "Inteligência Artificial", "Negócios", "Tráfego Pago",
    "Instagram", "TikTok Ads", "IA Generativa", "Automação"
]


# ─── FUNÇÕES DE BUSCA ────────────────────────────────────────────

async def fetch_reddit(url: str, client_http: httpx.AsyncClient) -> list[dict]:
    try:
        headers = {"User-Agent": "wavy-scout-bot/1.0"}
        resp = await client_http.get(url, headers=headers, timeout=10)
        data = resp.json()
        posts = []
        for post in data.get("data", {}).get("children", []):
            p = post["data"]
            posts.append({
                "title": p.get("title", ""),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "score": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "source": "Reddit"
            })
        return posts
    except Exception as e:
        print(f"Erro Reddit {url}: {e}")
        return []


async def fetch_rss(url: str, client_http: httpx.AsyncClient) -> list[dict]:
    try:
        resp = await client_http.get(url, timeout=10, follow_redirects=True)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            link  = item.findtext("link", "")
            if title and link:
                items.append({
                    "title": title.strip(),
                    "url": link.strip(),
                    "score": 0,
                    "comments": 0,
                    "source": url.split("/")[2]
                })
        return items[:5]
    except Exception as e:
        print(f"Erro RSS {url}: {e}")
        return []


async def collect_all_content() -> list[dict]:
    all_content = []
    async with httpx.AsyncClient() as http:
        tasks = []
        for source in SOURCES:
            if "reddit.com" in source:
                tasks.append(fetch_reddit(source, http))
            else:
                tasks.append(fetch_rss(source, http))

        results = await asyncio.gather(*tasks)
        for result in results:
            all_content.extend(result)

    return all_content


# ─── ANÁLISE COM CLAUDE ──────────────────────────────────────────

def analyze_trends_with_claude(raw_content: list[dict], excluded_titles: list[str] = None) -> list[dict]:
    """
    Usa Claude para analisar o conteúdo e retornar top 5 trends.
    Se excluded_titles for passado, Claude evita sugerir temas similares.
    """
    content_summary = "\n".join([
        f"- [{item['source']}] {item['title']} (score: {item.get('score', 0)}, comments: {item.get('comments', 0)})"
        for item in raw_content[:80]
    ])

    today = datetime.now().strftime("%d/%m/%Y")

    # Bloco de exclusão — só aparece se houver temas anteriores
    exclusion_block = ""
    if excluded_titles:
        lista = "\n".join(f"- {t}" for t in excluded_titles)
        exclusion_block = f"""
IMPORTANTE: Os temas abaixo JÁ FORAM mostrados ao usuário nesta sessão. 
NÃO repita nem sugira temas similares ou relacionados a eles:
{lista}

Traga ângulos completamente diferentes — outros tópicos, outras plataformas, outros problemas.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""Você é um analista de tendências de marketing digital especializado em conteúdo viral para Instagram.

Data de hoje: {today}
{exclusion_block}
Abaixo estão os títulos e fontes coletados de blogs, Reddit e feeds de marketing digital nas últimas horas:

{content_summary}

Sua tarefa:
1. Identifique as TOP 5 tendências mais relevantes e virais nos temas: {', '.join(TOPICS)}
2. Para cada trend, atribua um score de viralidade de 0 a 100 baseado em:
   - Relevância para criadores de conteúdo de marketing/negócios no Brasil
   - Potencial de engajamento no Instagram
   - Novidade e timing (algo que está explodindo agora)
   - Aplicabilidade para pequenos e médios empreendedores

Retorne APENAS um JSON válido neste formato (sem explicações, sem markdown):
{{
  "trends": [
    {{
      "titulo": "Título claro e descritivo da trend em português",
      "descricao": "2-3 frases explicando o que está acontecendo e por que é relevante agora",
      "topico": "Meta Ads | Google Ads | Marketing Digital | IA | Negócios",
      "score_viralidade": 85,
      "angulos_sugeridos": [
        "Ângulo 1 para carrossel ou reels",
        "Ângulo 2 para carrossel ou reels",
        "Ângulo 3 para carrossel ou reels"
      ],
      "fonte": "Nome da fonte original"
    }}
  ],
  "data_coleta": "{today}",
  "total_fontes_analisadas": {len(raw_content)}
}}"""
        }]
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Erro ao parsear JSON do Claude: {e}")
        return {"trends": [], "data_coleta": today, "total_fontes_analisadas": 0}


# ─── SALVAR NO NOTION ────────────────────────────────────────────

async def save_to_notion(trends_data: dict):
    if not NOTION_TOKEN or not NOTION_DB_TRENDS:
        print("⚠️  Notion não configurado — pulando salvamento.")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    async with httpx.AsyncClient() as http:
        for trend in trends_data.get("trends", []):
            payload = {
                "parent": {"database_id": NOTION_DB_TRENDS},
                "properties": {
                    "Título": {
                        "title": [{"text": {"content": trend["titulo"]}}]
                    },
                    "Descrição": {
                        "rich_text": [{"text": {"content": trend["descricao"]}}]
                    },
                    "Tópico": {
                        "select": {"name": trend["topico"]}
                    },
                    "Score Viralidade": {
                        "number": trend["score_viralidade"]
                    },
                    "Fonte": {
                        "rich_text": [{"text": {"content": trend["fonte"]}}]
                    },
                    "Status": {
                        "select": {"name": "Nova"}
                    },
                    "Data Coleta": {
                        "date": {"start": datetime.now().strftime("%Y-%m-%d")}
                    }
                }
            }
            try:
                resp = await http.post(
                    "https://api.notion.com/v1/pages",
                    headers=headers,
                    json=payload
                )
                if resp.status_code == 200:
                    print(f"✅ Trend salva no Notion: {trend['titulo']}")
                else:
                    print(f"❌ Erro Notion: {resp.status_code} — {resp.text}")
            except Exception as e:
                print(f"Erro ao salvar no Notion: {e}")


# ─── EXECUTAR SCOUT ──────────────────────────────────────────────

async def run_scout(excluded_titles: list[str] = None) -> dict:
    """
    Função principal do Agente 1.
    excluded_titles: lista de títulos já mostrados — Claude evitará repetir.
    """
    print("🔍 Agente 1 — Scout iniciado...")
    print(f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    if excluded_titles:
        print(f"🚫 Excluindo {len(excluded_titles)} temas já vistos")
    print("📡 Coletando conteúdo das fontes...")

    raw_content = await collect_all_content()
    print(f"✅ {len(raw_content)} itens coletados de {len(SOURCES)} fontes")

    print("🧠 Analisando tendências com Claude...")
    trends_data = analyze_trends_with_claude(raw_content, excluded_titles=excluded_titles)
    print(f"✅ {len(trends_data.get('trends', []))} trends identificadas")

    print("📝 Salvando no Notion...")
    await save_to_notion(trends_data)

    print("\n" + "="*50)
    print("📊 TOP 5 TRENDS:")
    print("="*50)
    for i, trend in enumerate(trends_data.get("trends", []), 1):
        print(f"\n{i}. {trend['titulo']}")
        print(f"   📌 Tópico: {trend['topico']}")
        print(f"   🔥 Score: {trend['score_viralidade']}/100")
        print(f"   📝 {trend['descricao']}")

    return trends_data


if __name__ == "__main__":
    result = asyncio.run(run_scout())
    with open("/tmp/trends_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n✅ Scout finalizado. Resultado salvo em /tmp/trends_result.json")
