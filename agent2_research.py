"""
AGENTE 2 — RESEARCH AGENT v1
Recebe o payload do post viral e realiza 4–6 buscas web estratégicas
via Claude + web_search tool. Monta briefing estruturado com dados,
dores, insights e hooks sugeridos para o Copy Agent.
"""

import os
import json
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── BUSCAS ESTRATÉGICAS ──────────────────────────────────────────────────────

BUSCA_PROMPT = """Você é um research agent especialista em marketing de conteúdo viral.
Recebeu o seguinte post viral como referência:

TEMA: {tema}
COPY DE REFERÊNCIA:
{copy_ref}

Seu objetivo é fazer EXATAMENTE 5 buscas web ESTRATÉGICAS para coletar dados reais que vão
enriquecer a criação de conteúdo novo sobre esse tema. Não faça mais nem menos que 5 buscas.

REGRAS DAS BUSCAS:
- Busca 1: DADOS NUMÉRICOS (estatísticas, pesquisas, percentuais)
- Busca 2: DORES REAIS do público (reclamações, frustrações, problemas)
- Busca 3: TENDÊNCIAS recentes (últimos 3 meses)
- Busca 4: ARGUMENTOS CONTRÁRIOS (o que as pessoas questionam sobre esse tema)
- Busca 5: CASOS DE SUCESSO concretos (exemplos reais com números)
- Varie os termos: use inglês e português, termos técnicos e populares

Para cada busca, salve a URL da fonte principal encontrada.

Execute as 5 buscas agora e retorne um JSON com a estrutura:
{
  "buscas_realizadas": [
    {"query": "...", "resultado_resumo": "...", "url_fonte": "https://...", "dados_uteis": ["...", "..."]}
  ],
  "tema_central": "...",
  "subtemas_descobertos": ["..."],
  "urls_profundidade": ["https://fonte1.com", "https://fonte2.com", "https://fonte3.com", "https://fonte4.com", "https://fonte5.com"],
  "dados_impactantes": ["Dado 1 com fonte", "Dado 2 com fonte"],
  "dores_publico": ["Dor 1", "Dor 2", "Dor 3"],
  "insights_exclusivos": ["Insight 1", "Insight 2"],
  "hooks_sugeridos": [
    {"tipo": "dado chocante", "hook": "..."},
    {"tipo": "pergunta incômoda", "hook": "..."},
    {"tipo": "afirmação polêmica", "hook": "..."}
  ],
  "angulos_possiveis": [
    {"titulo": "...", "abordagem": "...", "diferencial": "..."},
    {"titulo": "...", "abordagem": "...", "diferencial": "..."},
    {"titulo": "...", "abordagem": "...", "diferencial": "..."}
  ]
}

Retorne APENAS o JSON, sem markdown, sem explicações."""


BRIEFING_PROMPT = """Você é um estrategista de conteúdo sênior.
Com base nas pesquisas realizadas, monte um briefing executivo para o copywriter.

DADOS DA PESQUISA:
{dados_pesquisa}

POST VIRAL DE REFERÊNCIA:
Tipo: {tipo_post}
Engajamento: {engajamento}
Copy: {copy_ref}

Monte o briefing seguindo EXATAMENTE essa estrutura:

## 📊 Briefing de Pesquisa — {tema}

**Contexto do mercado:**
[2-3 frases sobre o cenário atual do tema com dados reais]

**Dados que vão performar:**
• [Dado 1 com número/percentual]
• [Dado 2 com número/percentual]
• [Dado 3 com número/percentual]

**Dores do público-alvo:**
• [Dor 1 — linguagem coloquial como o público fala]
• [Dor 2]
• [Dor 3]

**O que o post viral fez certo:**
• [Elemento 1 de sucesso]
• [Elemento 2 de sucesso]

**Hooks sugeridos:**
1. 🔥 Dado chocante: "[hook]"
2. ❓ Pergunta incômoda: "[hook]"
3. 💣 Afirmação polêmica: "[hook]"

**Ângulos disponíveis:**
A) [Título ângulo A] — [uma linha de descrição]
B) [Título ângulo B] — [uma linha de descrição]
C) [Título ângulo C] — [uma linha de descrição]

**Instrução para o copywriter:**
[1-2 frases sobre como usar esses dados na copy, tom recomendado, formato ideal]"""


# ── EXECUÇÃO DA PESQUISA ─────────────────────────────────────────────────────

def executar_buscas(viral_payload: dict) -> dict:
    """Faz as buscas web via Claude com web_search tool."""
    post = viral_payload.get("post_viral", {})
    instrucoes = viral_payload.get("instrucoes_pipeline", {})

    tema = instrucoes.get("aprofundar_sobre") or post.get("analise", {}).get("tema_central", "")
    copy_ref = post.get("copy", {}).get("copy_consolidada", "")[:500]

    prompt = BUSCA_PROMPT.format(tema=tema, copy_ref=copy_ref)

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        # Extrai o texto da resposta
        texto = ""
        for block in response.content:
            if hasattr(block, "text"):
                texto += block.text

        # Tenta parsear o JSON
        try:
            inicio = texto.find("{")
            fim = texto.rfind("}") + 1
            if inicio >= 0 and fim > inicio:
                return json.loads(texto[inicio:fim])
        except json.JSONDecodeError:
            pass

        # Fallback: retorna estrutura básica
        return {
            "buscas_realizadas": [],
            "tema_central": tema,
            "subtemas_descobertos": [],
            "dados_impactantes": ["Pesquisa web não retornou dados estruturados"],
            "dores_publico": ["Dor 1", "Dor 2", "Dor 3"],
            "insights_exclusivos": [],
            "hooks_sugeridos": [],
            "angulos_possiveis": [],
            "texto_bruto": texto[:2000]
        }

    except Exception as e:
        print(f"[RESEARCH] Erro nas buscas: {e}")
        return {
            "erro": str(e),
            "tema_central": tema,
            "dados_impactantes": [],
            "dores_publico": [],
            "hooks_sugeridos": [],
            "angulos_possiveis": []
        }


def montar_briefing(dados_pesquisa: dict, viral_payload: dict) -> str:
    """Monta o briefing formatado via Claude."""
    post = viral_payload.get("post_viral", {})
    instrucoes = viral_payload.get("instrucoes_pipeline", {})

    tema = dados_pesquisa.get("tema_central") or instrucoes.get("aprofundar_sobre", "")
    tipo_post = post.get("tipo", "post")
    metricas = post.get("metricas", {})
    eng = f"{metricas.get('engajamento_pct', 0)}% eng · {metricas.get('likes', 0)} likes"
    copy_ref = post.get("copy", {}).get("copy_consolidada", "")[:400]
    dados_str = json.dumps(dados_pesquisa, ensure_ascii=False)[:3000]

    prompt = BRIEFING_PROMPT.format(
        dados_pesquisa=dados_str,
        tipo_post=tipo_post,
        engajamento=eng,
        copy_ref=copy_ref,
        tema=tema
    )

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[RESEARCH] Erro ao montar briefing: {e}")
        return f"## Briefing — {tema}\n\nErro ao gerar briefing: {e}"


# ── PAYLOAD DO BRIEFING ──────────────────────────────────────────────────────

def montar_payload_briefing(dados_pesquisa: dict, briefing_txt: str, viral_payload: dict) -> dict:
    """Monta o payload completo do research agent para o copy agent."""
    post = viral_payload.get("post_viral", {})
    instrucoes = viral_payload.get("instrucoes_pipeline", {})

    return {
        "briefing_pesquisa": {
            "tema_central": dados_pesquisa.get("tema_central", ""),
            "briefing_formatado": briefing_txt,
            "dados_impactantes": dados_pesquisa.get("dados_impactantes", []),
            "dores_publico": dados_pesquisa.get("dores_publico", []),
            "insights_exclusivos": dados_pesquisa.get("insights_exclusivos", []),
            "hooks_sugeridos": dados_pesquisa.get("hooks_sugeridos", []),
            "angulos_possiveis": dados_pesquisa.get("angulos_possiveis", []),
            "buscas_realizadas": len(dados_pesquisa.get("buscas_realizadas", [])),
            "subtemas": dados_pesquisa.get("subtemas_descobertos", []),
            "urls_profundidade": dados_pesquisa.get("urls_profundidade", []),
        },
        "post_viral": post,
        "instrucoes_pipeline": {
            **instrucoes,
            "copy_referencia": post.get("copy", {}).get("copy_consolidada", ""),
            "copy_completa": post.get("copy", {}),
        }
    }


# ── ENTRADA PRINCIPAL ────────────────────────────────────────────────────────

def run_research(viral_payload: dict = None) -> dict:
    """
    Executa o research agent completo.
    Se viral_payload for None, tenta carregar do arquivo /tmp/wavy_viral_payload.json.
    """
    if viral_payload is None:
        try:
            with open("/tmp/wavy_viral_payload.json", "r", encoding="utf-8") as f:
                viral_payload = json.load(f)
        except Exception as e:
            return {"erro": f"Payload do viral scraper não encontrado: {e}"}

    print("[RESEARCH] Iniciando buscas web...")
    dados = executar_buscas(viral_payload)

    print("[RESEARCH] Montando briefing...")
    briefing_txt = montar_briefing(dados, viral_payload)

    payload = montar_payload_briefing(dados, briefing_txt, viral_payload)

    # Salva para próximo agente
    with open("/tmp/wavy_briefing.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"[RESEARCH] Briefing pronto — {dados.get('buscas_realizadas', []).__len__()} buscas realizadas")
    return payload
