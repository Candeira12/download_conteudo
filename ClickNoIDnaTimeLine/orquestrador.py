from clique_timeline import (
    localizar_item_por_id,
    clicar_com_retry_inteligente,
)
from navegador import conectar_pagina_timeline
import logging
import time

logger = logging.getLogger(__name__)


def executar_clique_no_id(playwright, id_alvo, cdp_url):
    """
    Executa clique no ID com detecção de carregamento (não timeout fixo).
    
    Args:
        playwright: Instância do Playwright
        id_alvo: ID do elemento na timeline
        cdp_url: URL do Chrome DevTools Protocol
    
    Returns:
        dict com resultado detalhado da operação
    
    Raises:
        RuntimeError: Se ID não encontrado ou clique falhar após retries
    """
    logger.info("executar_clique_no_id: conectando ao navegador %s", cdp_url)
    browser, pagina = conectar_pagina_timeline(playwright, cdp_url)

    # Verifica se o item existe na timeline
    item = localizar_item_por_id(pagina, id_alvo)
    if item is None:
        logger.error("executar_clique_no_id: ID %s nao encontrado na timeline", id_alvo)
        raise RuntimeError(f"ID {id_alvo} nao encontrado na timeline.")

    # tenta obter texto e bounding box do item para logs
    trecho_item = ""
    bbox = None
    try:
        trecho_item = (item.inner_text() or "")[:500]
    except Exception:
        logger.exception("executar_clique_no_id: falha ao obter inner_text do item")
    try:
        # bounding_box pode retornar None se o elemento não estiver na viewport
        bbox = item.bounding_box()
    except Exception:
        logger.exception("executar_clique_no_id: falha ao obter bounding_box do item")

    logger.debug("executar_clique_no_id: item localizado. trecho=%s bbox=%s", (trecho_item or "")[:200], bbox)

    # Clica com retry inteligente (detecta quando carrega)
    dados_clique, estado_viz, tentativa_sucesso = clicar_com_retry_inteligente(
        pagina, 
        id_alvo,
        max_tentativas=3,
        delay_entre_ms=800
    )

    return {
        "id": id_alvo,
        "status": "sucesso",
        "mensagem": f"Clique confirmado no ID {id_alvo} na tentativa {tentativa_sucesso}.",
        "posicao_clique": {
            "x": dados_clique["x"],
            "y": dados_clique["y"],
        },
        "estrategia_clique": dados_clique.get("estrategia", "desconhecida"),
        "indice_item": dados_clique.get("indice_item", -1),
        "trecho_item": dados_clique.get("trecho_item", ""),
        "tentativa_sucesso": tentativa_sucesso,
        "estado_visualizador": estado_viz,
        "titulo_pagina": pagina.title(),
        "url_pagina": pagina.url,
        "diagnosticos_item": {
            "trecho_item_localizacao": (trecho_item or "")[:500],
            "bounding_box_item": bbox,
        }
    }