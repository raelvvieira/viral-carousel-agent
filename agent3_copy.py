"""
AGENTE 3 — COPY AGENT v3
Recebe briefing de pesquisa + post viral de referência.
Gera copy nova, original e viral — inspirada no post mas com
voz própria, dados reais da pesquisa e estrutura otimizada para
o formato escolhido (carrossel, post único, reel).
"""

import os
import json
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── PRINCÍPIOS DA COPY ───────────────────────────────────────────────────────

PRINCIPIOS = """
PRINCÍPIOS INVIOLÁVEIS DA COPY WAVY:

1. ORIGINALIDADE TOTAL — Inspire-se no viral, nunca copie. A copy deve ser 100% nova.

2. HOOK MAGNÉTICO — O slide 1 (ou primeiro parágrafo) precisa parar o scroll em 0,3s.
   Use dado chocante, pergunta que dói ou afirmação que divide opiniões.

3. DADOS REAIS — Cada claim precisa ter número, estudo ou fonte. Evite generalizações.

4. LINGUAGEM DO PÚBLICO — Escreva como o público fala, não como especialista escreve.
   Zero jargão técnico desnecessário. Zero formalidade.

5. TENSÃO CRESCENTE — Cada slide/parágrafo precisa criar curiosidade para o próximo.
   Use "mas espera..." / "só que tem um detalhe..." / "e aqui vem a virada:"

6. CTA ESPECÍFICO — Nunca "curta e siga". CTA concreto: "salva esse post",
   "manda pra quem precisa ouvir isso", "comenta qual é o seu caso".

7. TOM CONSISTENTE — Seja direto, humano e levemente irreverente. Zero corporativo.
"""

# ── PROMPTS POR FORMATO ──────────────────────────────────────────────────────

PROMPT_CARROSSEL = """Você é o Copy Agent v3 da Wavy, especialista em criar carrosséis virais para Instagram.

{principios}

BRIEFING DE PESQUISA:
{briefing}

POST VIRAL DE REFERÊNCIA (inspire-se, não copie):
{copy_referencia}

FORMATO: Carrossel de {num_slides} slides
TEMA: {tema}

Crie o carrossel completo. Cada slide tem:
- titulo: texto principal (máximo 8 palavras, impactante)
- corpo: desenvolvimento (máximo 40 palavras, claro e direto)
- prompt_imagem: descrição visual para gerar/buscar a imagem ideal desse slide
- tipo_slide: cover | conteudo | dado | virada | cta

ESTRUTURA OBRIGATÓRIA:
- Slide 1 (cover): Hook. Para o scroll. Faz a pessoa precisar ver o próximo.
- Slides 2-{penultimo}: Desenvolvimento com dados, dores e insights. Tensão crescente.
- Slide {ultimo} (cta): CTA específico + identidade de marca.

LEGENDA DO POST (para o campo "legenda"):
- Repete o hook do slide 1
- 3-4 linhas de valor
- CTA para salvar/compartilhar
- 5-8 hashtags relevantes

Retorne APENAS JSON nesse formato:
{{
  "slides": [
    {{
      "numero": 1,
      "tipo_slide": "cover",
      "titulo": "...",
      "corpo": "...",
      "prompt_imagem": "...",
      "notas_design": "..."
    }}
  ],
  "legenda": "...",
  "tema": "...",
  "num_slides": {num_slides},
  "formato": "carrossel"
}}"""

PROMPT_POST_UNICO = """Você é o Copy Agent v3 da Wavy, especialista em posts únicos virais para Instagram.

{principios}

BRIEFING DE PESQUISA:
{briefing}

POST VIRAL DE REFERÊNCIA (inspire-se, não copie):
{copy_referencia}

FORMATO: Post único
TEMA: {tema}

Crie um post único de alto impacto com:
- titulo: linha de texto sobreposta à imagem (máximo 10 palavras)
- corpo: texto secundário opcional (máximo 15 palavras)
- prompt_imagem: descrição visual da imagem ideal
- legenda: copy completa da legenda (hook + valor + CTA + hashtags)

A imagem precisa funcionar sozinha — sem a legenda. Texto visual forte.

Retorne APENAS JSON:
{{
  "slides": [
    {{
      "numero": 1,
      "tipo_slide": "cover",
      "titulo": "...",
      "corpo": "...",
      "prompt_imagem": "...",
      "notas_design": "..."
    }}
  ],
  "legenda": "...",
  "tema": "...",
  "num_slides": 1,
  "formato": "post_unico"
}}"""

PROMPT_REEL = """Você é o Copy Agent v3 da Wavy, especialista em roteiros de Reels virais para Instagram.

{principios}

BRIEFING DE PESQUISA:
{briefing}

POST VIRAL DE REFERÊNCIA (inspire-se, não copie):
{copy_referencia}

FORMATO: Roteiro de Reel (vídeo)
TEMA: {tema}

Crie um roteiro completo de Reel. Estrutura:
- duração ideal: 30-60 segundos
- cada bloco tem: tempo, fala (exata, como gravaria), nota_direção

ESTRUTURA OBRIGATÓRIA:
[0-3s] Hook de abertura — frase que para o scroll no primeiro frame
[3-15s] Problema/Agitação — aprofunda a dor do público
[15-35s] Desenvolvimento — dados, insights, virada
[35-50s] Solução/Conclusão — o que fazer com isso
[50-60s] CTA — ação específica

LEGENDA (para o campo "legenda"):
- Hook do reel
- 3 linhas de valor
- CTA para salvar/seguir
- Hashtags

Retorne APENAS JSON:
{{
  "roteiro": [
    {{
      "tempo": "0-3s",
      "fala": "...",
      "nota_direcao": "...",
      "tipo": "hook"
    }}
  ],
  "legenda": "...",
  "tema": "...",
  "duracao_estimada": "45s",
  "formato": "reel",
  "slides": [],
  "num_slides": 0
}}"""


# ── GERAÇÃO DE COPY ──────────────────────────────────────────────────────────

def gerar_copy(briefing_payload: dict, formato: str = "carrossel", num_slides: int = 7) -> dict:
    """Gera a copy completa via Claude."""
    briefing = briefing_payload.get("briefing_pesquisa", {})
    instrucoes = briefing_payload.get("instrucoes_pipeline", {})

    tema = briefing.get("tema_central") or instrucoes.get("aprofundar_sobre", "")
    briefing_txt = briefing.get("briefing_formatado", "")
    copy_ref = instrucoes.get("copy_referencia", "")[:400]

    if formato == "carrossel":
        prompt = PROMPT_CARROSSEL.format(
            principios=PRINCIPIOS,
            briefing=briefing_txt,
            copy_referencia=copy_ref,
            num_slides=num_slides,
            penultimo=num_slides - 1,
            ultimo=num_slides,
            tema=tema
        )
    elif formato == "post_unico":
        prompt = PROMPT_POST_UNICO.format(
            principios=PRINCIPIOS,
            briefing=briefing_txt,
            copy_referencia=copy_ref,
            tema=tema
        )
    elif formato == "reel":
        prompt = PROMPT_REEL.format(
            principios=PRINCIPIOS,
            briefing=briefing_txt,
            copy_referencia=copy_ref,
            tema=tema
        )
    else:
        return {"erro": f"Formato desconhecido: {formato}"}

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()

        # Extrai JSON
        inicio = texto.find("{")
        fim = texto.rfind("}") + 1
        if inicio >= 0 and fim > inicio:
            return json.loads(texto[inicio:fim])

        return {"erro": "Resposta sem JSON válido", "texto_bruto": texto[:1000]}

    except json.JSONDecodeError as e:
        return {"erro": f"Erro ao parsear JSON: {e}", "texto_bruto": texto[:1000]}
    except Exception as e:
        print(f"[COPY] Erro ao gerar copy: {e}")
        return {"erro": str(e)}


def ajustar_slide(copy_payload: dict, slide_num: int, instrucao: str) -> dict:
    """Reescreve um slide específico mantendo o restante."""
    slides = copy_payload.get("copy", {}).get("slides", [])
    if not slides or slide_num < 1 or slide_num > len(slides):
        return copy_payload

    slide_atual = slides[slide_num - 1]

    prompt = f"""Reescreva APENAS este slide do carrossel seguindo a instrução do usuário.

SLIDE ATUAL:
{json.dumps(slide_atual, ensure_ascii=False)}

INSTRUÇÃO DO USUÁRIO:
{instrucao}

{PRINCIPIOS}

Retorne APENAS o JSON do slide reescrito (mesmo formato):
{{
  "numero": {slide_num},
  "tipo_slide": "...",
  "titulo": "...",
  "corpo": "...",
  "prompt_imagem": "...",
  "notas_design": "..."
}}"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()
        inicio = texto.find("{")
        fim = texto.rfind("}") + 1
        novo_slide = json.loads(texto[inicio:fim])

        # Atualiza o slide no payload
        slides[slide_num - 1] = novo_slide
        copy_payload["copy"]["slides"] = slides
        return copy_payload

    except Exception as e:
        print(f"[COPY] Erro ao ajustar slide {slide_num}: {e}")
        return copy_payload


def formatar_copy_para_aprovacao(copy_data: dict) -> str:
    """Formata a copy gerada para apresentação ao usuário."""
    formato = copy_data.get("formato", "carrossel")
    tema = copy_data.get("tema", "")

    linhas = [f"✍️ Copy pronta — {formato.upper()} · {tema}\n"]
    linhas.append("─" * 40)

    if formato == "reel":
        linhas.append("\n🎬 ROTEIRO:\n")
        for bloco in copy_data.get("roteiro", []):
            linhas.append(
                f"[{bloco.get('tempo', '')}] {bloco.get('fala', '')}\n"
                f"   → {bloco.get('nota_direcao', '')}\n"
            )
    else:
        slides = copy_data.get("slides", [])
        for slide in slides:
            num = slide.get("numero", "?")
            tipo = slide.get("tipo_slide", "")
            titulo = slide.get("titulo", "")
            corpo = slide.get("corpo", "")
            linhas.append(f"📌 Slide {num} ({tipo})\n   {titulo}\n   {corpo}\n")

    legenda = copy_data.get("legenda", "")
    if legenda:
        linhas.append("─" * 40)
        linhas.append(f"\n📝 LEGENDA:\n{legenda}\n")

    return "\n".join(linhas)


# ── PAYLOAD FINAL ────────────────────────────────────────────────────────────

def montar_payload_copy(copy_data: dict, briefing_payload: dict, formato: str, num_slides: int) -> dict:
    """Monta o payload completo para o próximo agente."""
    briefing = briefing_payload.get("briefing_pesquisa", {})

    return {
        "copy_aprovada": {
            "formato": formato,
            "num_slides": num_slides,
            "tema": copy_data.get("tema", briefing.get("tema_central", "")),
            "slides": copy_data.get("slides", []),
            "roteiro": copy_data.get("roteiro", []),
            "legenda": copy_data.get("legenda", ""),
            "duracao_estimada": copy_data.get("duracao_estimada"),
            "copy_formatada": formatar_copy_para_aprovacao(copy_data)
        },
        "briefing_pesquisa": briefing_payload.get("briefing_pesquisa", {}),
        "post_viral": briefing_payload.get("post_viral", {}),
        "instrucoes_pipeline": briefing_payload.get("instrucoes_pipeline", {})
    }


# ── ENTRADA PRINCIPAL ────────────────────────────────────────────────────────

def run_copy_agent(briefing_payload: dict = None, formato: str = "carrossel", num_slides: int = 7) -> dict:
    """
    Executa o copy agent completo.
    Se briefing_payload for None, tenta carregar de /tmp/wavy_briefing.json.
    """
    if briefing_payload is None:
        try:
            with open("/tmp/wavy_briefing.json", "r", encoding="utf-8") as f:
                briefing_payload = json.load(f)
        except Exception as e:
            return {"erro": f"Briefing não encontrado: {e}"}

    print(f"[COPY] Gerando copy — formato: {formato}, slides: {num_slides}...")
    copy_data = gerar_copy(briefing_payload, formato, num_slides)

    if "erro" in copy_data:
        return copy_data

    payload = montar_payload_copy(copy_data, briefing_payload, formato, num_slides)

    # Salva para próximo agente
    with open("/tmp/wavy_copy.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    total = len(copy_data.get("slides", [])) or len(copy_data.get("roteiro", []))
    print(f"[COPY] Copy pronta — {total} elementos gerados")
    return payload
