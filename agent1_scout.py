"""
AGENTE 1 - SCOUT
Monitora tendencias virais em IA, Negocios, Marketing Digital, Meta, Vendas e Tecnologia.
Publico-alvo: donos de negocios brasileiros descobrindo IA e marketing digital.
"""

import os
import json
import asyncio
import httpx
from datetime import datetime
from anthropic import Anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NOTION_TOKEN      = os.getenv("NOTION_TOKEN")
NOTION_DB_TRENDS  = os.getenv("NOTION_DB_TRENDS")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

#     FONTES RSS                                                   
RSS_SOURCES = [
    # Marketing e Ads
    "https://feeds.feedburner.com/socialmediaexaminer",
    "https://blog.hootsuite.com/feed/",
    "https://www.jonloomer.com/feed/",
    "https://searchengineland.com/feed",
    "https://adespresso.com/blog/feed/",
    # IA e Tecnologia
    "https://openai.com/news/rss.xml",
    "https://www.anthropic.com/rss.xml",
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    # Negocios e Empreendedorismo
    "https://hbr.org/stories.rss",
    "https://www.inc.com/rss/homepage.xml",
    "https://feeds.feedburner.com/entrepreneur/latest",
    "https://www.fastcompany.com/latest/rss",
    # Instagram e Meta
    "https://about.fb.com/feed/",
    "https://developers.facebook.com/blog/feed/",
]

#     FONTES REDDIT                                                
REDDIT_SOURCES = [
    # Marketing e Ads
    "https://www.reddit.com/r/FacebookAds/top.json?limit=15&t=week",
    "https://www.reddit.com/r/PPC/top.json?limit=15&t=week",
    "https://www.reddit.com/r/marketing/top.json?limit=15&t=week",
    "https://www.reddit.com/r/digital_marketing/top.json?limit=10&t=week",
    # IA e Negocios
    "https://www.reddit.com/r/artificial/top.json?limit=15&t=week",
    "https://www.reddit.com/r/ChatGPT/top.json?limit=15&t=week",
    "https://www.reddit.com/r/OpenAI/top.json?limit=10&t=week",
    "https://www.reddit.com/r/ClaudeAI/top.json?limit=10&t=week",
    # Empreendedorismo
    "https://www.reddit.com/r/Entrepreneur/top.json?limit=15&t=week",
    "https://www.reddit.com/r/smallbusiness/top.json?limit=10&t=week",
    "https://www.reddit.com/r/startups/top.json?limit=10&t=week",
    # Vendas
    "https://www.reddit.com/r/sales/top.json?limit=10&t=week",
]

TOPICS = [
    "IA para Negocios (OpenAI, Anthropic, Google, Claude, ChatGPT)",
    "Automacao e produtividade com IA",
    "Novidades de produtos de IA que mudam o mercado",
    "Meta Ads, Instagram e Facebook para negocios",
    "Trafego Pago e performance de anuncios",
    "Estrategias de vendas e conversao",
    "Marketing de conteudo e crescimento organico",
    "Cases de empresas que inovaram ou cresceram muito",
    "Historias de empresas que falharam e o que aprender",
    "Movimentos de mercado (fusoes, aquisicoes, pivotas, falencias)",
    "Estrategias de grandes marcas (Apple, Nike, Amazon, Tesla, Meta, etc)",
    "Startups e empresas brasileiras em destaque",
    "Tendencias de consumo e comportamento do mercado",
    "Economia e impacto nos pequenos e medios negocios",
    "Empreendedorismo e gestao de negocios",
    "E-commerce e vendas digitais",
]

PUBLICO = """
O Instagram da Wavy e seguido por pessoas que precisam ou se interessam por marketing e vendas:
- Donos de pequenos e medios negocios (qualquer setor) que querem vender mais
- Profissionais liberais (medicos, advogados, dentistas, coaches, consultores) construindo autoridade
- Gestores de marketing e times de vendas
- Agencias e freelancers de trafego pago
- Infoprodutores e criadores de conteudo que vivem de audiencia
- E-commerces querendo escalar
- Pessoas curiosas sobre negocios, mercado e tecnologia

O canal tambem funciona como FONTE DE NOTICIAS DE NEGOCIOS - cases de empresas, movimentos de
mercado, estrategias de grandes marcas. Quem segue porque la sempre tem algo novo e relevante
sobre o que esta acontecendo no mundo dos negocios, mesmo que nao tenha relacao direta com marketing.
A sensacao deve ser: preciso seguir a Wavy para nao ficar por fora.
"""


#     BUSCA REDDIT                                                 

async def fetch_reddit(url: str, client_http: httpx.AsyncClient) -> list[dict]:
    try:
        headers = {"User-Agent": "wavy-scout-bot/1.0"}
        resp = await client_http.get(url, headers=headers, timeout=15)
        data = resp.json()
        posts = []
        for post in data.get("data", {}).get("children", []):
            p = post["data"]
            # Filtra posts muito curtos ou sem engajamento
            if p.get("score", 0) < 10:
                continue
            posts.append({
                "title": p.get("title", ""),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "score": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "source": f"Reddit r/{url.split('/r/')[1].split('/')[0]}"
            })
        return posts
    except Exception as e:
        print(f"Erro Reddit {url}: {e}")
        return []


#     BUSCA RSS                                                    

async def fetch_rss(url: str, client_http: httpx.AsyncClient) -> list[dict]:
    try:
        resp = await client_http.get(url, timeout=15, follow_redirects=True)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            link  = item.findtext("link", "")
            if title and link and len(title) > 15:
                items.append({
                    "title": title.strip(),
                    "url": link.strip(),
                    "score": 0,
                    "comments": 0,
                    "source": url.split("/")[2].replace("www.", "").replace("feeds.feedburner.com/", "")
                })
        return items[:8]
    except Exception as e:
        print(f"Erro RSS {url}: {e}")
        return []


#     COLETA PARALELA                                              

async def collect_all_content() -> list[dict]:
    all_content = []
    all_sources = RSS_SOURCES + REDDIT_SOURCES

    async with httpx.AsyncClient() as http:
        tasks = []
        for source in all_sources:
            if "reddit.com" in source:
                tasks.append(fetch_reddit(source, http))
            else:
                tasks.append(fetch_rss(source, http))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                all_content.extend(result)

    # Ordena por engajamento (Reddit por score, RSS fica com 0)
    all_content.sort(key=lambda x: x.get("score", 0) + x.get("comments", 0) * 2, reverse=True)
    return all_content


#     ANALISE COM CLAUDE                                           

def analyze_trends_with_claude(raw_content: list[dict], excluded_titles: list[str] = None) -> dict:
    """Analisa o conteudo coletado e retorna top 5 trends para o publico da Wavy."""

    # Prioriza os mais engajados + pega variedade de fontes
    top_content = raw_content[:100]

    content_summary = "\n".join([
        f"- [{item['source']}] {item['title']} (engajamento: {item.get('score', 0) + item.get('comments', 0) * 2})"
        for item in top_content
    ])

    today = datetime.now().strftime("%d/%m/%Y")

    exclusion_block = ""
    if excluded_titles:
        lista = "\n".join(f"- {t}" for t in excluded_titles)
        exclusion_block = f"""
ATENCAO: Os temas abaixo JA FORAM mostrados ao usuario nesta sessao.
NAO repita nem sugira temas similares ou relacionados:
{lista}

Traga angulos completamente diferentes - outros topicos, outros problemas, outras empresas.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        messages=[{
            "role": "user",
            "content": f"""Voce e um curador de conteudo viral especializado no mercado brasileiro de negocios e marketing digital.

Data de hoje: {today}

PUBLICO-ALVO DA WAVY:
{PUBLICO}

TEMAS DE INTERESSE:
{chr(10).join(f"- {t}" for t in TOPICS)}

{exclusion_block}

CONTEUDO COLETADO (ordenado por engajamento):
{content_summary}

SUA TAREFA:
Identifique as TOP 5 melhores historias/tendencias para virar carrossel no Instagram da Wavy.
Misture os tipos - nao traga so dicas de marketing, traga variedade: uma noticia de empresa,
uma sobre IA, uma sobre vendas, uma sobre estrategia, etc.

CRITERIOS DE SELECAO:
1. Potencial de parar o scroll - titulo que provoca curiosidade ou espanto
2. Potencial de salvar e compartilhar - conteudo que as pessoas guardam para usar depois
3. Timing - algo que esta acontecendo AGORA ou explodiu recentemente
4. Angulo nao obvio - a perspectiva que a maioria nao esta vendo
5. Amplitude - pode ser pratico, pode ser inspiracional, pode ser so uma noticia boa de contar

TIPOS DE CONTEUDO QUE PERFORMAM MUITO:
- Cases de empresas: "Como a [empresa] fez X e cresceu Y%" (Nike, Apple, Amazon, startups)
- Noticias de IA com impacto real: lancamentos, mudancas de mercado, o que muda para negocios
- Movimentos de mercado: empresa que quebrou, foi vendida, pivotou, inovou
- Mudancas no Meta/Instagram que afetam quem anuncia ou cria conteudo
- Numeros e dados chocantes: "X% das empresas fazem isso errado", "mercado de Y vale R$ Z bi"
- Contraintuicoes: "o que voce acredita sobre X esta completamente errado"
- Estrategias de vendas e marketing com resultado comprovado
- Historias de empreendedores (sucesso ou fracasso) com licao clara

Retorne APENAS JSON valido sem markdown:
{{
  "trends": [
    {{
      "titulo": "Titulo impactante em portugues, como manchete de revista de negocios",
      "descricao": "2-3 frases explicando o que esta acontecendo, por que importa agora e o angulo surpreendente",
      "topico": "um dos topicos listados acima",
      "score_viralidade": 85,
      "angulos_sugeridos": [
        "Angulo 1: qual e o hook principal e por que vai parar o scroll",
        "Angulo 2: outro angulo diferente do mesmo tema",
        "Angulo 3: terceiro angulo com abordagem diferente"
      ],
      "fonte": "Nome da fonte original",
      "por_que_agora": "Uma frase explicando o timing - por que postar isso ESTA SEMANA"
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
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        print(f"Erro ao parsear JSON: {e}")
        return {"trends": [], "data_coleta": today, "total_fontes_analisadas": 0}


#     SALVAR NO NOTION                                             

async def save_to_notion(trends_data: dict):
    if not NOTION_TOKEN or not NOTION_DB_TRENDS:
        print("Notion nao configurado - pulando.")
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
                    "Titulo": {"title": [{"text": {"content": trend["titulo"]}}]},
                    "Descricao": {"rich_text": [{"text": {"content": trend["descricao"]}}]},
                    "Topico": {"select": {"name": trend["topico"]}},
                    "Score Viralidade": {"number": trend["score_viralidade"]},
                    "Fonte": {"rich_text": [{"text": {"content": trend["fonte"]}}]},
                    "Status": {"select": {"name": "Nova"}},
                    "Data Coleta": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}}
                }
            }
            try:
                resp = await http.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
                if resp.status_code == 200:
                    print(f"Trend salva no Notion: {trend['titulo']}")
            except Exception as e:
                print(f"Erro Notion: {e}")


#     EXECUTAR SCOUT                                               

async def run_scout(excluded_titles: list[str] = None) -> dict:
    """
    Funcao principal do Agente 1.
    excluded_titles: titulos ja mostrados - Claude evita repetir.
    """
    total_sources = len(RSS_SOURCES) + len(REDDIT_SOURCES)
    print(f"Agente 1 - Scout iniciado")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"Fontes: {len(RSS_SOURCES)} RSS + {len(REDDIT_SOURCES)} Reddit = {total_sources} total")
    if excluded_titles:
        print(f"Excluindo {len(excluded_titles)} temas ja vistos")

    raw_content = await collect_all_content()
    print(f"{len(raw_content)} itens coletados")

    print("Analisando com Claude...")
    trends_data = analyze_trends_with_claude(raw_content, excluded_titles=excluded_titles)
    count = len(trends_data.get("trends", []))
    print(f"{count} trends identificadas")

    await save_to_notion(trends_data)

    for i, trend in enumerate(trends_data.get("trends", []), 1):
        print(f"{i}. [{trend['score_viralidade']}/100] {trend['titulo']}")

    return trends_data


if __name__ == "__main__":
    result = asyncio.run(run_scout())
    with open("/tmp/trends_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("Scout finalizado.")
