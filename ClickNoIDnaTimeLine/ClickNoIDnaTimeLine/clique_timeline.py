"""
Orquestrador enxuto: expõe executar_clique_no_id(playwright, id_alvo, cdp_url).
Integrado com session_keeper para manter cookies entre execuções.
"""
import logging
import sys
import os

from navegador import conectar_pagina_timeline
from locator import localizar_item_por_id
from clicker import clicar_com_retry_inteligente

# Importa session_keeper do diretório pai
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session_keeper import salvar_cookies_sessao, restaurar_cookies_sessao

logger = logging.getLogger(__name__)


def executar_clique_no_id(playwright, id_alvo, cdp_url, numero_processo=None):
    """
    Executa clique em um ID da timeline com persistência de sessão.
    
    Args:
        playwright: Instância do Playwright
        id_alvo: ID a clicar
        cdp_url: URL de conexão CDP do navegador
        numero_processo: Número do processo para uso de cache de localizações
    
    Returns:
        dict com resultado da execução
    """
    logger.info("executar_clique_no_id: conectando ao navegador %s", cdp_url)
    browser, pagina = conectar_pagina_timeline(playwright, cdp_url)
    
    url_pagina = pagina.url
    logger.debug(f"Página carregada: {url_pagina}")
    
    # PASSO 1: Restaurar cookies da execução anterior (sem reload)
    logger.info("Restaurando cookies e estado de sessão...")
    resultado_restauracao = restaurar_cookies_sessao(pagina, url_pagina)
    logger.debug(f"Restauração: {resultado_restauracao}")
    
    # Aguarda um pouco para os cookies/storage serem processados
    pagina.wait_for_timeout(500)
    
    # Verifica existência do item na timeline
    logger.info(f"Localizando item com ID {id_alvo} na timeline...")
    item = localizar_item_por_id(pagina, id_alvo, numero_processo=numero_processo)
    if item is None:
        logger.error("executar_clique_no_id: ID %s nao encontrado na timeline", id_alvo)
        raise RuntimeError(f"ID {id_alvo} nao encontrado na timeline.")

    # Tenta clicar com lógica de retry e monitoramento do visualizador
    logger.info(f"Executando clique no ID {id_alvo}...")
    dados_clique, estado_viz, tentativa_sucesso = clicar_com_retry_inteligente(
        pagina,
        id_alvo,
        max_tentativas=3,
        delay_entre_ms=800,
    )
    
    # PASSO 2: Salvar cookies após execução bem-sucedida
    logger.info("Salvando cookies e estado de sessão...")
    resultado_salvamento = salvar_cookies_sessao(pagina, url_pagina)
    logger.debug(f"Salvamento: {resultado_salvamento}")

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
        "gerenciamento_sessao": {
            "restauracao": resultado_restauracao,
            "salvamento": resultado_salvamento,
            "nota": "Cookies e sessionStorage preservados para próxima execução"
        },
    }

    return resultado
