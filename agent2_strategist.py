"""
AGENTE 2 - ESTRATEGISTA
Recebe a trend escolhida, pede escolha de template, gera 3 angulos alinhados com o tom
do template, envia pro Telegram e aguarda escolha do angulo.

Fluxo:
  1. Envia mensagem pedindo template (A / B / C)
  2. Aguarda usuario escolher
  3. Gera 3 angulos com tom alinhado ao template escolhido
  4. Envia angulos pro Telegram
  5. Aguarda escolha do angulo
"""

import os
import json
import asyncio
from anthropic import Anthropic
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = int(os.getenv("TELEGRAM_CHAT_ID"))

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Evento global para angulo - scheduler.py seta quando usuario clica
_angulo_escolhido   = None
_aguardando_angulo  = asyncio.Event()

# Evento global para template - scheduler.py seta quando usuario clica
_template_escolhido  = None
_aguardando_template = asyncio.Event()

# Descricao de cada template para o Claude
TEMPLATE_DESCRICOES = {
    "A": {
        "nome": "Cinematico",
        "emoji": " ",
        "tom": "jornalistico, denso, investigativo. Narrativa com peso, ancoras de credibilidade, dados impactantes.",
        "ideal_para": "noticias de mercado, cases de empresas, dados chocantes, movimentos corporativos",
        "copy_style": "Copy mais longa, cada slide e um paragrafo jornalistico. Estilo: reportagem de revista de negocios.",
    },
    "B": {
        "nome": "Feed Claro",
        "emoji": "  ",
        "tom": "acessivel, didatico, proximo. Como um amigo especialista explicando algo importante.",
        "ideal_para": "dicas praticas, estrategias de marketing, como fazer, passo a passo, ferramentas",
        "copy_style": "Copy direta, linguagem proxima, cada slide e uma ideia clara. Estilo: post educativo do Instagram.",
    },
    "C": {
        "nome": "Editorial Escuro",
        "emoji": " ",
        "tom": "filosofico, provocativo, denso. Verdades que incomodam. Frases que pesam.",
        "ideal_para": "reflexoes de negocios, contraintuiticoes, mentalidade, criticas ao mercado",
        "copy_style": "Copy curta e impactante. Cada slide e uma frase que machuca ou ilumina. Estilo: aforismo de negocios.",
    },
}


def reset_strategist():
    """Reseta estado para nova execucao."""
    global _angulo_escolhido, _aguardando_angulo, _template_escolhido, _aguardando_template
    _angulo_escolhido   = None
    _template_escolhido = None
    # Limpa os eventos sem recriar - mantém a mesma referência
    _aguardando_angulo.clear()
    _aguardando_template.clear()


def set_template_escolhido(template: str):
    """Chamado pelo scheduler.py quando usuario clica em um template."""
    global _template_escolhido
    _template_escolhido = template
    _aguardando_template.set()


def set_angulo_escolhido(angulo: dict):
    """Chamado pelo scheduler.py quando usuario clica em um angulo."""
    global _angulo_escolhido
    _angulo_escolhido = angulo
    _aguardando_angulo.set()


async def send_template_choice(trend: dict):
    """Envia mensagem pedindo para o usuario escolher o template."""
    bot = Bot(token=TELEGRAM_TOKEN)

    texto = (
        f"Trend escolhida:\n*{trend['titulo']}*\n\n"
        f"Antes de gerar os angulos, escolha o *estilo visual* do carrossel.\n\n"
        f"  *Template A - Cinematico*\n"
        f"Fundo preto, imagem de fundo no slide 1, visual pesado\n"
        f"_Ideal para: noticias de mercado, cases de empresas_\n\n"
        f"   *Template B - Feed Claro*\n"
        f"Fundo cinza claro, estilo post do Instagram, cards de imagem\n"
        f"_Ideal para: dicas, estrategias, como fazer_\n\n"
        f"  *Template C - Editorial Escuro*\n"
        f"Fundo preto total, tipografia enorme, visual editorial\n"
        f"_Ideal para: reflexoes, provocacoes, mentalidade_\n\n"
        f"Qual template quer usar?"
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("  Template A", callback_data="template_A"),
        InlineKeyboardButton("   Template B", callback_data="template_B"),
        InlineKeyboardButton("  Template C", callback_data="template_C"),
    ]])

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=texto,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


def generate_angles_with_claude(trend: dict, template: str) -> dict:
    """Gera 3 angulos de conteudo alinhados com o tom do template escolhido."""
    t = TEMPLATE_DESCRICOES.get(template, TEMPLATE_DESCRICOES["A"])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Voce e um estrategista de conteudo viral para Instagram.

Trend identificada:
- Titulo: {trend['titulo']}
- Descricao: {trend['descricao']}
- Topico: {trend['topico']}
- Score de viralidade: {trend['score_viralidade']}/100

Template visual escolhido: {template} - {t['nome']}
Tom deste template: {t['tom']}
Ideal para: {t['ideal_para']}
Estilo de copy: {t['copy_style']}

IMPORTANTE: Os 3 angulos gerados devem ser coerentes com o tom e estilo do template {template}.
Nao gere angulos didaticos para o template C, nem angulos filosoficos para o template B.
Cada angulo deve encaixar naturalmente no visual e tom do template escolhido.

Gere 3 angulos DIFERENTES entre si, mas todos alinhados com o tom do template {template}.

Retorne APENAS JSON valido (sem markdown, sem explicacoes):
{{
  "trend_titulo": "{trend['titulo']}",
  "template": "{template}",
  "angulos": [
    {{
      "numero": 1,
      "titulo": "Titulo do angulo em portugues",
      "formato": "carrossel",
      "hook": "Frase de abertura impactante para o slide 1 (max 10 palavras)",
      "emocao": "identificacao",
      "descricao": "2-3 frases explicando a abordagem e por que vai viralizar",
      "perfil_alvo": "Para quem e esse angulo"
    }},
    {{
      "numero": 2,
      "titulo": "Titulo do angulo 2",
      "formato": "carrossel",
      "hook": "Hook do angulo 2",
      "emocao": "surpresa",
      "descricao": "Descricao do angulo 2",
      "perfil_alvo": "Perfil alvo 2"
    }},
    {{
      "numero": 3,
      "titulo": "Titulo do angulo 3",
      "formato": "carrossel",
      "hook": "Hook do angulo 3",
      "emocao": "indignacao",
      "descricao": "Descricao do angulo 3",
      "perfil_alvo": "Perfil alvo 3"
    }}
  ]
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
    except Exception as e:
        print(f"Erro ao parsear angulos: {e}")
        return {"angulos": []}


async def send_angles_to_telegram(trend: dict, angles_data: dict, template: str):
    """Envia os 3 angulos pro Telegram com botoes de escolha."""
    bot     = Bot(token=TELEGRAM_TOKEN)
    angulos = angles_data.get("angulos", [])
    t       = TEMPLATE_DESCRICOES.get(template, TEMPLATE_DESCRICOES["A"])

    texto = f"*{t['emoji']} Template {template} - {t['nome']}*\n\n"
    texto += f"3 angulos para:\n*{trend['titulo']}*\n\n"

    for i, angulo in enumerate(angulos[:3]):
        texto += f"{i+1}. *{angulo['titulo']}*\n"
        texto += f"_Hook: {angulo['hook'][:80]}_\n"
        texto += f"Tom: {angulo['emocao']} | Para: {angulo['perfil_alvo']}\n\n"

    texto += "Qual angulo quer desenvolver?"

    botoes = [
        InlineKeyboardButton(f"{i+1} {angulo['titulo'][:35]}", callback_data=f"angulo_{i}")
        for i, angulo in enumerate(angulos[:3])
    ]
    keyboard = InlineKeyboardMarkup([botoes])

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=texto,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def run_strategist(trends_data: dict, selected_index: int = 0) -> dict:
    """
    Funcao principal do Agente 2.
    1. Pede escolha de template
    2. Gera angulos alinhados com o template
    3. Aguarda escolha do angulo
    Retorna dict com 'trend', 'angulo', 'template' e 'formato'.
    """
    global _angulo_escolhido, _aguardando_angulo, _template_escolhido, _aguardando_template

    reset_strategist()

    print("Agente 2 - Estrategista iniciado...")

    trends = trends_data.get("trends", [])
    if selected_index >= len(trends):
        print(f"Indice {selected_index} invalido, usando 0")
        selected_index = 0

    trend = trends[selected_index]
    print(f"Trend escolhida: {trend['titulo']}")

    # Os botoes de template ja foram enviados pelo scheduler antes desta chamada
    # Apenas aguarda o usuario clicar
    print("Aguardando escolha do template no Telegram...")

    try:
        await asyncio.wait_for(_aguardando_template.wait(), timeout=600)
    except asyncio.TimeoutError:
        print("Timeout: nenhum template escolhido em 10 minutos, usando Template A")
        _template_escolhido = "A"

    template = _template_escolhido or "A"
    print(f"Template escolhido: {template}")

    # Gera angulos com o tom do template
    print(f"Gerando angulos para template {template}...")
    angles_data = generate_angles_with_claude(trend, template)
    angulos     = angles_data.get("angulos", [])

    if not angulos:
        print("Erro: nenhum angulo gerado")
        return None

    print(f"{len(angulos)} angulos gerados")

    # Salva para o callback do scheduler
    with open("/tmp/angles_data.json", "w", encoding="utf-8") as f:
        json.dump({"trend": trend, "angulos": angulos, "template": template}, f, ensure_ascii=False, indent=2)

    # Envia angulos pro Telegram
    await send_angles_to_telegram(trend, angles_data, template)

    print("Aguardando escolha do angulo no Telegram...")
    try:
        await asyncio.wait_for(_aguardando_angulo.wait(), timeout=600)
    except asyncio.TimeoutError:
        print("Timeout: nenhum angulo escolhido em 10 minutos")
        return None

    if not _angulo_escolhido:
        return None

    print(f"Angulo escolhido: {_angulo_escolhido['titulo']}")

    return {
        "trend":    trend,
        "angulo":   _angulo_escolhido,
        "template": template,
        "formato":  "carrossel"
    }


if __name__ == "__main__":
    try:
        with open("/tmp/trends_result.json", "r", encoding="utf-8") as f:
            trends = json.load(f)
    except FileNotFoundError:
        print("Rode o agent1_scout.py primeiro.")
        exit(1)

    result = asyncio.run(run_strategist(trends, selected_index=0))
    if result:
        print(f"Template: {result['template']} | Angulo: {result['angulo']['titulo']}")
