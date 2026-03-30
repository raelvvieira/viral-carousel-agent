"""
AGENTE 2 — RESEARCH AGENT v2
Recebe o payload completo do Agent 1 (copy intacta) e realiza 5 buscas web
para ganhar profundidade sobre o tema. Output: copy_completa + resumo_pesquisa (1 parágrafo).
"""

import os
import json
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── PROMPT DE BUSCA ──────────────────────────────────────────────────────────

BUSCA_PROMPT = """Você é um research agent. Recebeu o conteúdo completo de um post viral:

COPY DO POST:
{copy_ref}

Faça EXATAMENTE 5 buscas web sobre o tema central desse conteúdo para ganhar profundidade.
Busque dados, contexto, notícias recentes, exemplos e fatos que aprofundem o tema.
Varie os termos de busca: use português e inglês, termos técnicos e populares.

Retorne um JSON com a seguinte estrutura:
{{
  "tema_central": "...",
  "buscas": [
    {{"query": "...", "resumo": "resumo do que foi encontrado nessa busca"}}
  ]
}}

Retorne APENAS o JSON, sem markdown, sem explicações."""


# ── EXECUÇÃO DAS BUSCAS ──────────────────────────────────────────────────────

def executar_buscas(viral_payload: dict) -> dict:
    """Faz 5 buscas web via Claude com web_search tool usando a copy completa."""
    post = viral_payload.get("post_viral", {})
    copy_ref = post.get("copy", {}).get("copy_consolidada", "")

    prompt = BUSCA_PROMPT.format(copy_ref=copy_ref)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        texto = ""
        for block in response.content:
            if hasattr(block, "text"):
                texto += block.text

        try:
            inicio = texto.find("{")
            fim = texto.rfind("}") + 1
            if inicio >= 0 and fim > inicio:
                return json.loads(texto[inicio:fim])
        except json.JSONDecodeError:
            pass

        return {
            "tema_central": "",
            "buscas": [],
            "texto_bruto": texto[:2000]
        }

    except Exception as e:
        print(f"[RESEARCH] Erro nas buscas: {e}")
        return {"tema_central": "", "buscas": [], "erro": str(e)}


# ── RESUMO DA PESQUISA ───────────────────────────────────────────────────────

def montar_resumo_pesquisa(dados_busca: dict, viral_payload: dict) -> str:
    """Gera um parágrafo de resumo da pesquisa via Claude."""
    copy_ref = viral_payload.get("post_viral", {}).get("copy", {}).get("copy_consolidada", "")
    buscas_txt = json.dumps(dados_busca.get("buscas", []), ensure_ascii=False)

    prompt = f"""Com base nas buscas realizadas sobre o tema do post abaixo, escreva UM parágrafo
(5-8 frases) resumindo o que foi encontrado. Foque em dados, contexto e informações
que aprofundam o tema. Seja direto e informativo.

COPY DO POST:
{copy_ref[:1000]}

RESULTADOS DAS BUSCAS:
{buscas_txt[:3000]}

Retorne APENAS o parágrafo, sem título, sem bullet points."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[RESEARCH] Erro ao montar resumo: {e}")
        return f"Pesquisa realizada sobre: {dados_busca.get('tema_central', 'tema do post')}."


# ── PAYLOAD DO BRIEFING ──────────────────────────────────────────────────────

def montar_payload_briefing(dados_busca: dict, resumo: str, viral_payload: dict) -> dict:
    """Monta payload com copy_completa + resumo_pesquisa para os agentes seguintes."""
    post = viral_payload.get("post_viral", {})
    instrucoes = viral_payload.get("instrucoes_pipeline", {})

    return {
        "copy_completa": post.get("copy", {}),
        "resumo_pesquisa": resumo,
        "tema_central": dados_busca.get("tema_central", ""),
        "post_viral": post,
        "instrucoes_pipeline": instrucoes,
    }


# ── ENTRADA PRINCIPAL ────────────────────────────────────────────────────────

def run_research(viral_payload: dict = None) -> dict:
    """
    Executa o research agent completo.
    Se viral_payload for None, tenta carregar de /tmp/wavy_viral_payload.json.
    """
    if viral_payload is None:
        try:
            with open("/tmp/wavy_viral_payload.json", "r", encoding="utf-8") as f:
                viral_payload = json.load(f)
        except Exception as e:
            return {"erro": f"Payload do viral scraper não encontrado: {e}"}

    print("[RESEARCH] Executando buscas web...")
    dados = executar_buscas(viral_payload)

    print("[RESEARCH] Montando resumo da pesquisa...")
    resumo = montar_resumo_pesquisa(dados, viral_payload)

    payload = montar_payload_briefing(dados, resumo, viral_payload)

    with open("/tmp/wavy_briefing.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"[RESEARCH] Concluído — {len(dados.get('buscas', []))} buscas, resumo gerado")
    return payload
