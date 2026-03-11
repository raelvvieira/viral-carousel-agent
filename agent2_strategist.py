"""
AGENTE 2 - ESTRATEGISTA
Recebe a trend escolhida, gera 3 angulos de conteudo,
envia pro Telegram com botoes e aguarda escolha do angulo.
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

# Evento global - scheduler.py seta quando usuario clica no angulo
_angulo_escolhido = None
_aguardando_angulo = asyncio.Event()

# Evento global - scheduler.py seta quando usuario clica no template
_template_escolhido  = None
_aguardando_template = asyncio.Event()

TEMPLATE_DESCRICOES = {
    "A": "Cinematico — jornalistico, denso, dados impactantes",
    "B": "Feed Claro — acessivel, didatico, linguagem proxima",
    "C": "Editorial Escuro — filosofico, provocativo, frases de impacto",
}


def reset_strategist():
    """Reseta estado para nova execucao."""
    global _angulo_escolhido, _aguardando_angulo, _template_escolhido, _aguardando_template
    _angulo_escolhido  = None
    _aguardando_angulo = asyncio.Event()
    _template_escolhido  = None
    _aguardando_template = asyncio.Event()


def set_angulo_escolhido(angulo: dict):
    """Chamado pelo scheduler.py quando usuario clica em um angulo."""
    global _angulo_escolhido
    _angulo_escolhido = angulo
    _aguardando_angulo.set()


def set_template_escolhido(template: str):
    """Chamado pelo scheduler.py quando usuario clica em um template."""
    global _template_escolhido
    _template_escolhido = template
    _aguardando_template.set()


async def send_template_choice(trend: dict, angulo: dict):
    """Envia botoes de escolha de template apos o angulo ser selecionado."""
    bot = Bot(token=TELEGRAM_TOKEN)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("A - Cinematico",       callback_data="template_A"),
        InlineKeyboardButton("B - Feed Claro",       callback_data="template_B"),
        InlineKeyboardButton("C - Editorial Escuro", callback_data="template_C"),
    ]])
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            f"Angulo aprovado!\n\n"
            f"Qual visual voce quer para o carrossel?\n\n"
            f"A - Cinematico\nJornalistico, denso, dados impactantes\n\n"
            f"B - Feed Claro\nAcessivel, didatico, linguagem proxima\n\n"
            f"C - Editorial Escuro\nFilosofico, provocativo, frases de impacto"
        ),
        reply_markup=keyboard
    )


def generate_angles_with_claude(trend: dict) -> dict:
    """Gera 3 angulos de conteudo para a trend escolhida."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Voce e um estrategista de conteudo viral para Instagram especializado em Marketing Digital, Meta Ads, Google Ads, IA e Negocios.

Trend identificada:
- Titulo: {trend['titulo']}
- Descricao: {trend['descricao']}
- Topico: {trend['topico']}
- Score de viralidade: {trend['score_viralidade']}/100

Sua tarefa: gerar 3 angulos de conteudo viral DIFERENTES para essa trend.
O formato e SEMPRE carrossel de 10 slides.

Retorne APENAS um JSON valido neste formato (sem markdown, sem explicacoes):
{{
  "trend_titulo": "{trend['titulo']}",
  "angulos": [
    {{
      "numero": 1,
      "titulo": "Titulo do angulo em portugues",
      "formato": "carrossel",
      "hook": "Frase de abertura impactante para o slide 1",
      "emocao": "identificacao",
      "descricao": "2-3 frases explicando a abordagem e por que vai viralizar",
      "perfil_alvo": "Empreendedores que gastam em trafego"
    }},
    {{
      "numero": 2,
      "titulo": "Titulo do angulo 2",
      "formato": "carrossel",
      "hook": "Hook do angulo 2",
      "emocao": "surpresa",
      "descricao": "Descricao do angulo 2",
      "perfil_alvo": "Gestores de trafego"
    }},
    {{
      "numero": 3,
      "titulo": "Titulo do angulo 3",
      "formato": "carrossel",
      "hook": "Hook do angulo 3",
      "emocao": "indigna cao",
      "descricao": "Descricao do angulo 3",
      "perfil_alvo": "Donos de negocio digital"
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


async def send_angles_to_telegram(trend: dict, angles_data: dict):
    """Envia os 3 angulos pro Telegram com botoes de escolha."""
    bot     = Bot(token=TELEGRAM_TOKEN)
    angulos = angles_data.get("angulos", [])
    emojis  = ["1", "2", "3"]

    texto = f"Trend selecionada:\n*{trend['titulo']}*\n\n"
    texto += "Aqui estao os 3 angulos sugeridos:\n\n"

    for i, angulo in enumerate(angulos[:3]):
        texto += f"{emojis[i]}. *{angulo['titulo']}*\n"
        texto += f"Hook: _{angulo['hook'][:80]}_\n"
        texto += f"Emocao: {angulo['emocao']} | Para: {angulo['perfil_alvo']}\n\n"

    texto += "Qual angulo quer desenvolver?"

    botoes = [
        InlineKeyboardButton(f"{emojis[i]} {angulo['titulo'][:35]}", callback_data=f"angulo_{i}")
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
    Recebe trends_data e o indice da trend ja escolhida pelo usuario.
    Retorna dict com 'trend' e 'angulo' escolhidos.
    """
    global _angulo_escolhido, _aguardando_angulo, _template_escolhido, _aguardando_template

    # Reseta estado
    reset_strategist()

    print("Agente 2 - Estrategista iniciado...")

    trends = trends_data.get("trends", [])
    if selected_index >= len(trends):
        print(f"Indice {selected_index} invalido, usando 0")
        selected_index = 0

    trend = trends[selected_index]
    print(f"Trend escolhida: {trend['titulo']}")

    # Gera angulos com Claude
    print("Gerando angulos com Claude...")
    angles_data = generate_angles_with_claude(trend)
    angulos = angles_data.get("angulos", [])

    if not angulos:
        print("Erro: nenhum angulo gerado")
        return None

    print(f"{len(angulos)} angulos gerados")

    # Salva angulos para o callback do scheduler usar
    with open("/tmp/angles_data.json", "w", encoding="utf-8") as f:
        json.dump({"trend": trend, "angulos": angulos}, f, ensure_ascii=False, indent=2)

    # Envia pro Telegram com botoes
    await send_angles_to_telegram(trend, angles_data)

    # Aguarda usuario clicar em um angulo (timeout 10 minutos)
    print("Aguardando escolha do angulo no Telegram...")
    try:
        await asyncio.wait_for(_aguardando_angulo.wait(), timeout=600)
    except asyncio.TimeoutError:
        print("Timeout: nenhum angulo escolhido em 10 minutos")
        return None

    if not _angulo_escolhido:
        return None

    print(f"Angulo escolhido: {_angulo_escolhido['titulo']}")

    # Pede escolha do template visual
    await send_template_choice(trend, _angulo_escolhido)
    print("Aguardando escolha do template no Telegram...")
    try:
        await asyncio.wait_for(_aguardando_template.wait(), timeout=600)
    except asyncio.TimeoutError:
        print("Timeout: nenhum template escolhido em 10 minutos, usando A")
        _template_escolhido = "A"

    template = _template_escolhido or "A"
    print(f"Template escolhido: {template}")

    return {
        "trend":    trend,
        "angulo":   _angulo_escolhido,
        "template": template,
        "formato":  "carrossel",
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
        print(f"Escolha final: {result['angulo']['titulo']}")
