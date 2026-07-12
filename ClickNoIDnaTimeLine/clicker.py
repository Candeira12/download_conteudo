"""
Clicker module - Executes clicks on timeline items with multiple fallback strategies.
Handles retries and monitors visual feedback from clicks.
"""
import logging
import time

from locator import obter_alvo_de_clique_por_id
from monitor import aguardar_id_ativo_no_visualizador
from diagnostics import salvar_screenshot_path

logger = logging.getLogger(__name__)


def _obter_info_elemento(page, x, y):
    """
    Retorna informações do elemento em (x, y).
    """
    try:
        script = """
        (args) => {
            const { x, y } = args;
            const el = document.elementFromPoint(x, y);
            if (!el) return null;
            
            const anchor = el.closest ? el.closest('a') : null;
            return {
                tag: el.tagName,
                outerHTML: (el.outerHTML || '').slice(0, 1500),
                href: anchor ? (anchor.getAttribute('href') || '') : '',
                onclick: anchor ? (anchor.getAttribute('onclick') || '') : '',
                text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 300)
            };
        }
        """
        
        info = page.evaluate(script, {"x": x, "y": y})
        return info
    except Exception as e:
        logger.debug(f"Falha ao obter info do elemento: {e}")
        return None


def _executar_clique_js(page, x, y):
    """
    Clica via JavaScript no ponto (x, y).
    """
    try:
        script = """
        (args) => {
            const { x, y } = args;
            const el = document.elementFromPoint(x, y);
            if (!el) return false;
            
            // Tenta click() primeiro (mais confiável)
            if (typeof el.click === 'function') {
                el.click();
                return true;
            }
            
            // Fallback: simula eventos de mouse
            const evDown = new MouseEvent('mousedown', {
                bubbles: true,
                cancelable: true,
                clientX: x,
                clientY: y
            });
            const evUp = new MouseEvent('mouseup', {
                bubbles: true,
                cancelable: true,
                clientX: x,
                clientY: y
            });
            
            el.dispatchEvent(evDown);
            el.dispatchEvent(evUp);
            return true;
        }
        """
        
        resultado = page.evaluate(script, {"x": x, "y": y})
        return bool(resultado)
    except Exception as e:
        logger.debug(f"Falha ao clicar via JS: {e}")
        return False


def _executar_clique_mouse(page, x, y):
    """
    Clica usando mouse events do Playwright.
    """
    try:
        page.mouse.move(x, y)
        page.mouse.down()
        page.wait_for_timeout(50)
        page.mouse.up()
        return True
    except Exception as e:
        logger.debug(f"Falha ao clicar com mouse: {e}")
        return False


def _buscar_element_handle_otimizado(page, id_alvo, indice_item):
    """
    Busca um element_handle clicável dentro do item especificado.
    """
    try:
        itens = page.query_selector_all(".timeline .media")
        if not isinstance(indice_item, int) or indice_item >= len(itens):
            return None
        
        item = itens[indice_item]
        
        # Procura por elementos que contenham o ID ou linkem para /documento/download/
        seletores = ["a", "button", "[role='button']", ".ui-commandlink", "[onclick]"]
        for seletor in seletores:
            candidatos = item.query_selector_all(seletor)
            for candidato in candidatos:
                try:
                    href = candidato.get_attribute("href") or ""
                    texto = (candidato.inner_text() or "").strip()
                except Exception:
                    href = ""
                    texto = ""
                
                if (id_alvo and id_alvo in href) or \
                   ("/documento/download/" in href) or \
                   (id_alvo and id_alvo in texto):
                    return candidato
        
        return None
    except Exception as e:
        logger.debug(f"Falha ao buscar element_handle: {e}")
        return None


def clicar_id_com_mouse(page, id_alvo):
    """
    Executa clique em elemento contendo o ID.
    Retorna informações sobre o clique executado.
    """
    logger.info(f"Procurando elemento para clicar: ID {id_alvo}")
    
    alvo = obter_alvo_de_clique_por_id(page, id_alvo)
    x = float(alvo["x"])
    y = float(alvo["y"])
    
    logger.info(
        f"Clicando ID {id_alvo} em ({x:.1f}, {y:.1f}) - "
        f"estratégia: {alvo.get('estrategia')} índice: {alvo.get('indice_item')}"
    )
    
    # Screenshots
    pre_screenshot = salvar_screenshot_path(page, f"pre_click_{id_alvo}")
    
    # Info do elemento
    elem_info = _obter_info_elemento(page, x, y)
    logger.debug(f"Elemento em ({x}, {y}): {elem_info}")
    
    # Tenta clicar com múltiplas estratégias
    requests_capturados = []
    clicou = False
    
    def _on_request(req):
        try:
            requests_capturados.append(req.url)
        except Exception:
            pass
    
    page.on("request", _on_request)
    
    try:
        # Estratégia 1: Element handle direto (mais confiável)
        handle = _buscar_element_handle_otimizado(page, id_alvo, alvo.get("indice_item"))
        if handle:
            try:
                logger.debug("Tentando clicar via element_handle.click()")
                handle.click()
                clicou = True
                page.wait_for_timeout(300)
            except Exception as e:
                logger.debug(f"Falha no element_handle.click(): {e}")
                clicou = False
        
        # Estratégia 2: JavaScript click
        if not clicou:
            logger.debug("Tentando clicar via JavaScript")
            clicou = _executar_clique_js(page, x, y)
            if clicou:
                page.wait_for_timeout(300)
        
        # Estratégia 3: Mouse events
        if not clicou:
            logger.debug("Tentando clicar via mouse events")
            clicou = _executar_clique_mouse(page, x, y)
            if clicou:
                page.wait_for_timeout(300)
        
        page.wait_for_timeout(500)
        
    finally:
        try:
            page.off("request", _on_request)
        except Exception:
            pass
    
    # Screenshot pós-clique
    post_screenshot = salvar_screenshot_path(page, f"post_click_{id_alvo}")
    
    # Primeira request relevante
    primeiro_request = None
    for url in requests_capturados:
        if '/documento/download/' in url or id_alvo in url:
            primeiro_request = url
            break
    if not primeiro_request and requests_capturados:
        primeiro_request = requests_capturados[0]
    
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "estrategia": alvo.get("estrategia", "desconhecida"),
        "indice_item": alvo.get("indice_item", -1),
        "texto_item": (alvo.get("texto_item", "") or "")[:200],
        "screenshots": {"pre": pre_screenshot, "post": post_screenshot},
        "elemento_info": elem_info,
        "requests_capturados": requests_capturados,
        "request_principal": primeiro_request,
        "clicou": clicou,
    }


def clicar_com_retry_inteligente(page, id_alvo, max_tentativas=3, delay_ms=800):
    """
    Executa clique com retry automático.
    """
    ultima_excecao = None
    
    for tentativa in range(1, max_tentativas + 1):
        logger.info(f"Tentativa {tentativa}/{max_tentativas} para ID {id_alvo}")
        
        try:
            dados_clique = clicar_id_com_mouse(page, id_alvo)
            
            confirmou, estado_viz = aguardar_id_ativo_no_visualizador(
                page, id_alvo, timeout_ms=3000
            )
            
            if confirmou:
                logger.info(f"✓ Clique confirmado na tentativa {tentativa}")
                return dados_clique, estado_viz, tentativa
            
            logger.warning(
                f"Clique executado mas não confirmado na tentativa {tentativa}. "
                f"Estado: {estado_viz}"
            )
            
            if tentativa < max_tentativas:
                page.wait_for_timeout(delay_ms)
        
        except Exception as e:
            ultima_excecao = e
            logger.exception(f"Erro na tentativa {tentativa}: {e}")
            if tentativa < max_tentativas:
                page.wait_for_timeout(delay_ms)
    
    logger.error(f"✗ Falha após {max_tentativas} tentativas")
    
    # Coleta estado final
    try:
        _, estado_final = aguardar_id_ativo_no_visualizador(
            page, id_alvo, timeout_ms=2000
        )
    except Exception:
        estado_final = {"erro": "Não foi possível coletar estado final"}
    
    raise RuntimeError(
        f"Clique no ID {id_alvo} falhou após {max_tentativas} tentativas. "
        f"Último erro: {str(ultima_excecao)}. Estado final: {estado_final}"
    )
