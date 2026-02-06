#!/usr/bin/env python3
"""
🔥 GERADOR DE CARROSSÉIS VIRAIS - VERSÃO 3.0
Estratégia Profissional de Copy que FORÇA o Engajamento
Sistema: Tese → Acusação → Tensão → Prova → Virada → CTA
"""

import os
import json
from datetime import datetime
from typing import List, Dict
from anthropic import Anthropic
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)


class ViralCarouselEngine:
    """
    Motor de geração de carrosséis usando engenharia de copy viral
    Baseado na estratégia: parar → continuar → acreditar → salvar → comentar
    """

    def __init__(self, anthropic_api_key: str):
        self.client = Anthropic(api_key=anthropic_api_key)
        self.output_dir = "/tmp/carrosels_virais"
        os.makedirs(self.output_dir, exist_ok=True)

        self.brand_config = {
            "cores": {
                "primaria": "#0066FF",
                "secundaria": "#FF6B6B",
                "acento": "#FFD93D",
                "texto": "#1A1A1A",
                "fundo": "#FFFFFF"
            },
            "fontes": {
                "titulo": "Montserrat Bold",
                "corpo": "Inter Regular"
            }
        }

    def criar_prompt_viral_profissional(self, tema_base: str) -> str:
        estrategia_copy = """
# 🎯 ESTRATÉGIA DE COPY VIRAL - ENGENHARIA DE ENGAJAMENTO

Você é um MESTRE em criar carrosséis que PARAM O SCROLL usando engenharia de copy.

## FILOSOFIA CENTRAL

A "estratégia" aqui NÃO é escrever bonito. É construir um TRILHO MENTAL que FORÇA a pessoa a:
1) PARAR (capa que acusa/revela)
2) CONTINUAR (tensão progressiva)
3) ACREDITAR (prova em 3 formatos)
4) SALVAR (frases-lâmina memoráveis)
5) COMENTAR (CTA de continuidade)

---

## 📐 ESTRUTURA OBRIGATÓRIA

### SLIDE 1 - CAPA: ACUSAÇÃO OU REVELAÇÃO
REGRA DE OURO: Capa NÃO introduz. Capa ACUSA ou REVELA.

Fórmulas comprovadas:
- "[Grupo] está matando [indústria/hábito]..."
- "A [marca famosa] é uma [revelação contraintuitiva]..."
- "O fim do [padrão antigo]..."

Checklist da capa:
✅ Tem 1 ideia, 1 choque, 0 explicação
✅ Cria curiosidade através de CONTRADIÇÃO
✅ Promete resolver uma tensão

### SLIDE 2 - O CONTRATO
Objetivo: Dar contexto rápido + prometer payoff

### SLIDES 3-8 - PROGRESSÃO EDITORIAL
NÃO é lista de dicas. É PROGRESSÃO DE RACIOCÍNIO.

SLIDE 3: Nomeia o fenômeno
SLIDE 4: Explica POR QUÊ acontece
SLIDE 5: Mostra evidência de mercado
SLIDE 6: Dá o "modelo mental"
SLIDE 7: Prova FORTE
SLIDE 8: Traduz em implicação prática

## 🔥 TENSÃO: O MOTOR SECRETO
Use pelo menos 3 tipos de tensão:
1. Virada semântica
2. Paradoxo
3. Custo invisível
4. Ameaça cultural
5. Micro-suspense

## 📊 PROVA EM 3 FORMATOS
Formato A - Dado + Fonte
Formato B - Caso/Exemplo Reconhecível
Formato C - Frase-Lâmina (Memorável)

## ✍️ LINGUAGEM: CURTA, ADULTA, MARTELO
- Frases curtas (10-15 palavras MAX)
- Cortes secos
- Palavras com PESO
- Ritmo de martelo

## 🎯 CTA: CONTINUIDADE DE IDENTIDADE
NÃO peça: "Me siga", "Clique no link", "Curte aí"
PEÇA: Microcompromisso que continua o assunto

---

## 🔥 AGORA EXECUTE!

Use TODA essa metodologia para criar o carrossel sobre: "{tema_base}"

Retorne JSON com esta estrutura EXATA:

{{
    "tese_central": "A tese forte e comprável",
    "inimigo_implicito": "O que você está combatendo",
    "titulo_principal": "Título do carrossel",
    "gatilhos_usados": ["tensão 1", "tensão 2"],
    "legenda": "Legenda completa para o post",
    "slides": [
        {{
            "numero": 1,
            "tipo": "capa",
            "titulo": "TEXTO CAPS",
            "subtitulo": "revelação",
            "cor_fundo": "#0066FF",
            "checklist_capa": {{
                "tem_posicao_clara": true,
                "gera_curiosidade": true,
                "promete_resolver_tensao": true
            }}
        }},
        {{
            "numero": 2,
            "tipo": "contrato",
            "contexto": "cenário rápido",
            "promessa": "payoff prometido",
            "corpo": "texto completo"
        }},
        {{
            "numero": 3,
            "tipo": "fenomeno",
            "corpo": "texto do slide"
        }},
        {{
            "numero": 4,
            "tipo": "porque",
            "corpo": "texto do slide"
        }},
        {{
            "numero": 5,
            "tipo": "evidencia",
            "corpo": "texto do slide"
        }},
        {{
            "numero": 6,
            "tipo": "modelo_mental",
            "corpo": "texto do slide"
        }},
        {{
            "numero": 7,
            "tipo": "prova_forte",
            "corpo": "texto do slide"
        }},
        {{
            "numero": 8,
            "tipo": "implicacao",
            "corpo": "texto do slide"
        }},
        {{
            "numero": 9,
            "tipo": "cta",
            "corpo": "texto do CTA"
        }}
    ],
    "analise_viral": {{
        "frases_lamina": ["frase 1", "frase 2"],
        "viradas_semanticas": ["virada 1", "virada 2"],
        "prova_forte": "qual dado/caso usado",
        "potencial_salvar": "1-10 e por quê",
        "porque_vai_viralizar": "análise em 3 linhas"
    }}
}}
"""
        prompt = estrategia_copy + f"\n\n**TEMA BASE:** {tema_base}\n\nCrie o carrossel VIRAL seguindo TODA a metodologia acima!"
        return prompt

    def gerar_carrossel_viral(self, tema: str) -> Dict:
        prompt = self.criar_prompt_viral_profissional(tema)

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4500,
            temperature=0.9,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                carrossel = json.loads(json_str)
                return carrossel
            else:
                raise ValueError("JSON não encontrado na resposta")
        except Exception as e:
            return {"error": str(e), "raw_response": content[:500]}

    def _gerar_preview(self, carrossel: Dict) -> str:
        preview = "\n" + "=" * 70 + "\n"
        preview += "  📱 PREVIEW DO CARROSSEL VIRAL\n"
        preview += "=" * 70 + "\n\n"

        for slide in carrossel.get('slides', []):
            num = slide.get('numero', 0)
            tipo = slide.get('tipo', '').upper()
            preview += f"--- SLIDE {num:02d} - {tipo} ---\n"

            if tipo == "CAPA":
                titulo = slide.get('titulo', '')
                subtitulo = slide.get('subtitulo', '')
                preview += f"  {titulo}\n"
                if subtitulo:
                    preview += f"  {subtitulo}\n"
            else:
                corpo = slide.get('corpo', slide.get('contexto', ''))
                preview += f"  {corpo}\n"
            preview += "\n"

        return preview

    def _gerar_guia_imagens(self, carrossel: Dict) -> str:
        guia = "🎨 GUIA DE GERAÇÃO DE IMAGENS\n"
        guia += "=" * 70 + "\n\n"

        for slide in carrossel.get('slides', []):
            num = slide.get('numero', 0)
            guia += f"\nSLIDE {num:02d}\n"
            guia += "-" * 70 + "\n"
            guia += f"Tipo: {slide.get('tipo', 'N/A')}\n"
            guia += f"Cor de fundo: {slide.get('cor_fundo', self.brand_config['cores']['primaria'])}\n\n"

            if 'titulo' in slide:
                guia += f"TÍTULO: {slide['titulo']}\n"
            if 'corpo' in slide:
                guia += f"CORPO: {slide['corpo']}\n"
            if 'subtitulo' in slide:
                guia += f"SUBTÍTULO: {slide['subtitulo']}\n"
            guia += "\n"

        return guia

    def _gerar_relatorio_viral(self, carrossel: Dict) -> str:
        relatorio = "🔥 ANÁLISE DE VIRALIDADE\n"
        relatorio += "=" * 70 + "\n\n"

        relatorio += f"TESE CENTRAL:\n{carrossel.get('tese_central', 'N/A')}\n\n"
        relatorio += f"INIMIGO IMPLÍCITO:\n{carrossel.get('inimigo_implicito', 'N/A')}\n\n"

        analise = carrossel.get('analise_viral', {})

        relatorio += "FRASES-LÂMINA (Salvabilidade):\n"
        for frase in analise.get('frases_lamina', []):
            relatorio += f"  • {frase}\n"

        relatorio += "\nVIRADAS SEMÂNTICAS (Retenção):\n"
        for virada in analise.get('viradas_semanticas', []):
            relatorio += f"  • {virada}\n"

        relatorio += f"\nPROVA FORTE:\n{analise.get('prova_forte', 'N/A')}\n"
        relatorio += f"\nPOTENCIAL DE SALVAR: {analise.get('potencial_salvar', 'N/A')}/10\n"
        relatorio += f"\nPOR QUE VAI VIRALIZAR:\n{analise.get('porque_vai_viralizar', 'N/A')}\n"

        return relatorio

    def salvar_e_gerar_outputs(self, carrossel: Dict) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"viral_{timestamp}"

        json_path = os.path.join(self.output_dir, f"{base_filename}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(carrossel, indent=2, ensure_ascii=False, fp=f)

        preview = self._gerar_preview(carrossel)
        guia = self._gerar_guia_imagens(carrossel)
        analise = self._gerar_relatorio_viral(carrossel)

        return {
            "json_path": json_path,
            "preview": preview,
            "guia_imagens": guia,
            "analise_viral": analise
        }


# ==================== FLASK WEB APP ====================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 Gerador de Carrosséis Virais</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
        h1 {
            font-size: 2.5em;
            text-align: center;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #FF6B6B, #FFD93D, #0066FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle { text-align: center; color: #888; margin-bottom: 40px; font-size: 1.1em; }
        .input-section {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
        }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #FFD93D; }
        input[type="text"], textarea {
            width: 100%;
            padding: 14px 18px;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px;
            color: #fff;
            font-size: 16px;
            margin-bottom: 20px;
        }
        input[type="text"]:focus, textarea:focus {
            outline: none;
            border-color: #0066FF;
            box-shadow: 0 0 0 3px rgba(0,102,255,0.2);
        }
        .btn {
            display: block;
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #0066FF, #0044CC);
            color: #fff;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,102,255,0.4); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .loading { display: none; text-align: center; padding: 40px; }
        .loading.active { display: block; }
        .spinner {
            border: 4px solid rgba(255,255,255,0.1);
            border-top: 4px solid #0066FF;
            border-radius: 50%;
            width: 50px; height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .result { display: none; }
        .result.active { display: block; }
        .slide-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 16px;
            transition: transform 0.2s;
        }
        .slide-card:hover { transform: translateX(5px); }
        .slide-num {
            display: inline-block;
            background: #0066FF;
            color: #fff;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .slide-tipo {
            display: inline-block;
            background: rgba(255,107,107,0.2);
            color: #FF6B6B;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            margin-left: 8px;
        }
        .slide-content { color: #ccc; line-height: 1.7; white-space: pre-wrap; margin-top: 10px; }
        .analysis-box {
            background: rgba(255,215,61,0.05);
            border: 1px solid rgba(255,215,61,0.2);
            border-radius: 12px;
            padding: 24px;
            margin-top: 30px;
        }
        .analysis-box h3 { color: #FFD93D; margin-bottom: 15px; }
        .tag {
            display: inline-block;
            background: rgba(0,102,255,0.15);
            color: #66AAFF;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 13px;
            margin: 3px;
        }
        .legenda-box {
            background: rgba(0,102,255,0.05);
            border: 1px solid rgba(0,102,255,0.2);
            border-radius: 12px;
            padding: 24px;
            margin-top: 20px;
        }
        .legenda-box h3 { color: #0066FF; margin-bottom: 10px; }
        .copy-btn {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            margin-top: 10px;
        }
        .copy-btn:hover { background: rgba(255,255,255,0.2); }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 Gerador de Carrosséis Virais</h1>
        <p class="subtitle">Motor de Copy Viral com IA — Tese → Acusação → Tensão → Prova → Virada → CTA</p>

        <div class="input-section">
            <label>📌 Tema do Carrossel</label>
            <input type="text" id="tema" placeholder="Ex: Meta Ads virou o novo Google — mas ninguém percebeu">
            <label>🎯 Contexto Adicional (opcional)</label>
            <textarea id="contexto" rows="3" placeholder="Público-alvo, nicho, tom de voz..."></textarea>
            <button class="btn" id="gerarBtn" onclick="gerarCarrossel()">⚡ GERAR CARROSSEL VIRAL</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>🧠 Motor de Copy Viral processando...</p>
            <p style="color: #888; margin-top: 10px;">Aplicando: Tese → Acusação → Tensão → Prova → Virada → CTA</p>
        </div>

        <div class="result" id="result"></div>
    </div>

    <script>
        async function gerarCarrossel() {
            const tema = document.getElementById('tema').value;
            const contexto = document.getElementById('contexto').value;
            if (!tema) { alert('Digite um tema!'); return; }

            const btn = document.getElementById('gerarBtn');
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');

            btn.disabled = true;
            loading.classList.add('active');
            result.classList.remove('active');

            try {
                const response = await fetch('/gerar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tema, contexto })
                });
                const data = await response.json();

                if (data.error) {
                    result.innerHTML = '<div class="slide-card"><p style="color:#FF6B6B;">❌ Erro: ' + data.error + '</p></div>';
                } else {
                    renderResult(data);
                }
            } catch (err) {
                result.innerHTML = '<div class="slide-card"><p style="color:#FF6B6B;">❌ Erro de conexão: ' + err.message + '</p></div>';
            }

            btn.disabled = false;
            loading.classList.remove('active');
            result.classList.add('active');
        }

        function renderResult(data) {
            const c = data.carrossel;
            let html = '';

            html += '<div class="slide-card"><h3 style="color:#FFD93D;">📍 Tese Central</h3><p class="slide-content">' + (c.tese_central || '') + '</p></div>';
            html += '<div class="slide-card"><h3 style="color:#FF6B6B;">⚔️ Inimigo Implícito</h3><p class="slide-content">' + (c.inimigo_implicito || '') + '</p></div>';

            if (c.gatilhos_usados) {
                html += '<div class="slide-card"><h3>🎯 Gatilhos</h3><div>';
                c.gatilhos_usados.forEach(g => { html += '<span class="tag">' + g + '</span>'; });
                html += '</div></div>';
            }

            html += '<h2 style="margin: 30px 0 15px; color: #0066FF;">📱 Slides</h2>';

            if (c.slides) {
                c.slides.forEach(slide => {
                    html += '<div class="slide-card">';
                    html += '<span class="slide-num">SLIDE ' + slide.numero + '</span>';
                    html += '<span class="slide-tipo">' + (slide.tipo || '').toUpperCase() + '</span>';
                    if (slide.titulo) html += '<h3 style="margin-top:10px;color:#fff;">' + slide.titulo + '</h3>';
                    if (slide.subtitulo) html += '<p style="color:#FFD93D;margin-top:5px;">' + slide.subtitulo + '</p>';
                    if (slide.corpo) html += '<p class="slide-content">' + slide.corpo + '</p>';
                    if (slide.contexto) html += '<p class="slide-content">' + slide.contexto + '</p>';
                    if (slide.promessa) html += '<p style="color:#66AAFF;margin-top:8px;">💎 ' + slide.promessa + '</p>';
                    html += '</div>';
                });
            }

            if (c.legenda) {
                html += '<div class="legenda-box"><h3>📝 Legenda do Post</h3>';
                html += '<p class="slide-content" id="legendaText">' + c.legenda + '</p>';
                html += '<button class="copy-btn" onclick="copyText(\'legendaText\')">📋 Copiar Legenda</button></div>';
            }

            if (c.analise_viral) {
                const a = c.analise_viral;
                html += '<div class="analysis-box"><h3>🔥 Análise de Viralidade</h3>';
                if (a.frases_lamina) {
                    html += '<p style="font-weight:600;margin-top:10px;">💎 Frases-Lâmina:</p>';
                    a.frases_lamina.forEach(f => { html += '<p style="color:#FFD93D;margin:5px 0;">→ ' + f + '</p>'; });
                }
                if (a.viradas_semanticas) {
                    html += '<p style="font-weight:600;margin-top:15px;">🔄 Viradas Semânticas:</p>';
                    a.viradas_semanticas.forEach(v => { html += '<p style="color:#66AAFF;margin:5px 0;">→ ' + v + '</p>'; });
                }
                if (a.prova_forte) html += '<p style="margin-top:15px;"><strong>📊 Prova Forte:</strong> ' + a.prova_forte + '</p>';
                if (a.potencial_salvar) html += '<p><strong>💾 Potencial de Salvar:</strong> ' + a.potencial_salvar + '</p>';
                if (a.porque_vai_viralizar) html += '<p><strong>🚀 Por que vai viralizar:</strong> ' + a.porque_vai_viralizar + '</p>';
                html += '</div>';
            }

            document.getElementById('result').innerHTML = html;
        }

        function copyText(id) {
            const text = document.getElementById(id).innerText;
            navigator.clipboard.writeText(text).then(() => alert('Copiado!')).catch(() => alert('Erro ao copiar'));
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/gerar', methods=['POST'])
def gerar():
    data = request.get_json()
    tema = data.get('tema', '')
    contexto = data.get('contexto', '')

    if not tema:
        return jsonify({"error": "Tema é obrigatório"}), 400

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY não configurada"}), 500

    if contexto:
        tema = f"{tema}. Contexto: {contexto}"

    engine = ViralCarouselEngine(anthropic_api_key=api_key)
    carrossel = engine.gerar_carrossel_viral(tema)

    if "error" in carrossel:
        return jsonify({"error": carrossel["error"]}), 500

    outputs = engine.salvar_e_gerar_outputs(carrossel)

    return jsonify({
        "carrossel": carrossel,
        "preview": outputs["preview"],
        "analise": outputs["analise_viral"]
    })


@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "viral-carousel-agent"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
