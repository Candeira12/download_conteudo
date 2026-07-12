"""
Orquestrador enxuto: expõe executar_clique_no_id(playwright, id_alvo, cdp_url).
"""
import logging

from navegador import conectar_pagina_timeline
from locator import localizar_item_por_id
from clicker import clicar_com_retry_inteligente

logger = logging.getLogger(__name__)


def executar_clique_no_id(playwright, id_alvo, cdp_url):
    logger.info("executar_clique_no_id: conectando ao navegador %s", cdp_url)
    browser, pagina = conectar_pagina_timeline(playwright, cdp_url)

    # Verifica existência do item na timeline
    item = localizar_item_por_id(pagina, id_alvo)
    if item is None:
        logger.error("executar_clique_no_id: ID %s nao encontrado na timeline", id_alvo)
        raise RuntimeError(f"ID {id_alvo} nao encontrado na timeline.")

    # Tenta clicar com lógica de retry e monitoramento do visualizador
    dados_clique, estado_viz, tentativa_sucesso = clicar_com_retry_inteligente(
        pagina,
        id_alvo,
        max_tentativas=3,
        delay_entre_ms=800,
    )

    resultado = {
        "id": id_alvo,
        "status": "sucesso",
        "mensagem": f"Clique confirmado no ID {id_alvo} na tentativa {tentativa_sucesso}.",
        "posicao_clique": {"x": dados_clique["x"], "y": dados_clique["y"]},
        "estrategia_clique": dados_clique.get("estrategia", "desconhecida"),
        "indice_item": dados_clique.get("indice_item", -1),
        "trecho_item": dados_clique.get("trecho_item", ""),
        "tentativa_sucesso": tentativa_sucesso,
        "estado_visualizador": estado_viz,
        "titulo_pagina": pagina.title(),
        "url_pagina": pagina.url,
        "diagnosticos_click": {
            "screenshots": dados_clique.get("screenshots"),
            "element_from_point": dados_clique.get("element_from_point"),
            "requests_captured": dados_clique.get("requests_captured"),
            "clicked_via_js": dados_clique.get("clicked_via_js", False),
        },
    }

    return resultado