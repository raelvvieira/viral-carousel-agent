"""
AGENTE 2 - ESTRATEGISTA
Recebe a trend escolhida, pede escolha de template e retorna imediatamente
com o template escolhido + angulo base do Scout (sem chamada ao Claude).

Fluxo:
  1. Envia mensagem pedindo template (A / B / C)
  2. Aguarda usuario escolher
  3. Retorna trend + template + angulo base (do Scout)
"""

import os
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID  = int(os.getenv("TELEGRAM_CHAT_ID"))

# Evento global para template - scheduler.py seta quando usuario clica
_template_escolhido  = None
_aguardando_template = asyncio.Event()

# Descricao de cada template para o Copywriter
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
    global _template_escolhido, _aguardando_template
    _template_escolhido = None
    _aguardando_template.clear()


def set_template_escolhido(template: str):
    """Chamado pelo scheduler.py quando usuario clica em um template."""
    global _template_escolhido
    _template_escolhido = template
    _aguardando_template.set()


async def send_template_choice(trend: dict):
    """Envia mensagem pedindo para o usuario escolher o template."""
    bot = Bot(token=TELEGRAM_TOKEN)

    # Escapa caracteres especiais do Markdown v1 para evitar erro de parse
    titulo_safe = (trend['titulo']
                   .replace('\\', '\\\\')
                   .replace('*', '\\*')
                   .replace('_', '\\_')
                   .replace('[', '\\[')
                   .replace('`', '\\`'))

    texto = (
        f"Trend escolhida:\n*{titulo_safe}*\n\n"
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


async def run_strategist(trends_data: dict, selected_index: int = 0) -> dict:
    global _template_escolhido, _aguardando_template

    # Reset ANTES de qualquer coisa - garante eventos limpos
    reset_strategist()

    print("Agente 2 - Estrategista iniciado...")

    trends = trends_data.get("trends", [])
    if selected_index >= len(trends):
        selected_index = 0

    trend = trends[selected_index]
    print(f"Trend: {trend['titulo']}")

    # Envia botoes de template APOS o reset (ordem correta)
    await send_template_choice(trend)
    print("Aguardando template...")

    try:
        await asyncio.wait_for(_aguardando_template.wait(), timeout=600)
    except asyncio.TimeoutError:
        print("Timeout: nenhum template escolhido em 10 minutos, usando Template A")
        _template_escolhido = "A"

    template = _template_escolhido or "A"
    print(f"Template escolhido: {template}")

    # Usa o primeiro angulo sugerido pelo Scout como base (sem chamar Claude)
    angulos_sugeridos = trend.get("angulos_sugeridos", [])
    angulo_base = angulos_sugeridos[0] if angulos_sugeridos else trend.get("titulo", "")

    return {
        "trend":    trend,
        "template": template,
        "angulo":   {"titulo": angulo_base, "hook": "", "emocao": "", "perfil_alvo": ""},
        "formato":  "carrossel"
    }


if __name__ == "__main__":
    import json
    try:
        with open("/tmp/trends_result.json", "r", encoding="utf-8") as f:
            trends = json.load(f)
    except FileNotFoundError:
        print("Rode o agent1_scout.py primeiro.")
        exit(1)

    result = asyncio.run(run_strategist(trends, selected_index=0))
    if result:
        print(f"Template: {result['template']} | Angulo base: {result['angulo']['titulo']}")
