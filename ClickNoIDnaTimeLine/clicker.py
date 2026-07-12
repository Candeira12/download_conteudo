import logging
import time

from locator import obter_alvo_de_clique_por_id
from monitor import aguardar_id_ativo_no_visualizador
from diagnostics import salvar_screenshot_path

logger = logging.getLogger(__name__)


def _element_from_point_info(page, x, y):
    """Retorna um resumo do elemento em x,y (outerHTML curto, nearest anchor attrs)."""
    try:
        info = page.evaluate(
            """({x, y}) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return null;
                const a = el.closest ? el.closest('a') : null;
                return {
                    tag: el.tagName,
                    outerHTML: (el.outerHTML || '').slice(0, 2000),
                    a_href: a ? (a.getAttribute('href') || '') : '',
                    a_onclick: a ? (a.getAttribute('onclick') || '') : '',
                    text: (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim().slice(0,500)
                };
            }""",
            {"x": x, "y": y},
        )
        return info
    except Exception:
        logger.exception("_element_from_point_info: falha ao avaliar elementFromPoint")
        return None


def _click_candidate_handle(page, handle):
    """Clica com element_handle.click() e retorna após curto wait."""
    try:
        handle.click()
        # curto atraso para permitir requests serem disparadas
        page.wait_for_timeout(250)
        return True
    except Exception:
        logger.exception("_click_candidate_handle: falha ao clicar no element handle")
        return False


def clicar_id_com_mouse(page, id_alvo):
    alvo = obter_alvo_de_clique_por_id(page, id_alvo)

    x = float(alvo["x"])
    y = float(alvo["y"])

    logger.info(
        "clicar_id_com_mouse: clicando ID %s nas coordenadas x=%s y=%s estrategia=%s indice=%s",
        id_alvo, x, y, alvo.get("estrategia"), alvo.get("indice_item"),
    )

    pre_path = salvar_screenshot_path(page, f"pre_click_{id_alvo}")

    # elementFromPoint summary (safe evaluate with single arg)
    elem_info = _element_from_point_info(page, x, y)
    logger.debug("clicar_id_com_mouse: elementFromPoint info: %s", elem_info)

    # tenta clicar preferindo o anchor/button dentro do item (mais confiavel)
    requests_captured = []
    clicked_via_js = False
    candidate_clicked = False

    # registra listener para capturar requests durante o clique
    def _on_request(req):
        try:
            requests_captured.append(req.url)
        except Exception:
            pass

    page.on("request", _on_request)

    try:
        # tenta localizar item por indice e procurar candidatos confiaveis
        itens = page.query_selector_all(".timeline .media")
        candidate_handle = None
        try:
            idx = alvo.get("indice_item", None)
            if idx is not None and isinstance(idx, int) and idx < len(itens):
                item = itens[idx]
                # busca anchors/buttons que contenham id_alvo no href/texto ou que apontem para /documento/download/
                candidatos = item.query_selector_all("a, button, [role='button'], .ui-commandlink")
                for c in candidatos:
                    try:
                        href = c.get_attribute("href") or ""
                        texto = (c.inner_text() or "").strip()
                    except Exception:
                        href = ""
                        texto = ""
                    if (id_alvo and id_alvo in href) or ("/documento/download/" in (href or "")) or (id_alvo and id_alvo in texto):
                        candidate_handle = c
                        break
        except Exception:
            logger.exception("clicar_id_com_mouse: falha ao buscar candidate_handle dentro do item")

        if candidate_handle:
            logger.debug("clicar_id_com_mouse: candidate_handle encontrado, clicando via element_handle.click()")
            candidate_clicked = _click_candidate_handle(page, candidate_handle)
        else:
            # fallback: tenta disparar click via JS no point (mais robusto que mouse events em handlers)
            try:
                res = page.evaluate(
                    """({x, y}) => {
                        const el = document.elementFromPoint(x, y);
                        if (el) {
                            if (typeof el.click === 'function') {
                                el.click();
                                return true;
                            }
                            const evDown = new MouseEvent('mousedown', {bubbles:true, cancelable:true, clientX:x, clientY:y});
                            const evUp = new MouseEvent('mouseup', {bubbles:true, cancelable:true, clientX:x, clientY:y});
                            el.dispatchEvent(evDown);
                            el.dispatchEvent(evUp);
                            return true;
                        }
                        return false;
                    }""",
                    {"x": x, "y": y},
                )
                clicked_via_js = bool(res)
                candidate_clicked = clicked_via_js
            except Exception:
                logger.exception("clicar_id_com_mouse: falha ao executar clique via JS; usando eventos de mouse como ultimo recurso")
                try:
                    page.mouse.move(x, y)
                    page.mouse.down()
                    page.wait_for_timeout(40)
                    page.mouse.up()
                    candidate_clicked = True
                except Exception:
                    logger.exception("clicar_id_com_mouse: falha ao executar eventos de mouse")
                    candidate_clicked = False

        # após o clique, aguarda curtos instantes para requests aparecerem / UI reagir
        page.wait_for_timeout(500)
    finally:
        # remove listener
        try:
            page.off("request", _on_request)
        except Exception:
            pass

    post_path = salvar_screenshot_path(page, f"post_click_{id_alvo}")

    # pega a primeira request relevante (se houver)
    first_req = None
    for u in requests_captured:
        if '/documento/download/' in u or id_alvo in u:
            first_req = u
            break
    if not first_req and requests_captured:
        first_req = requests_captured[0]

    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "estrategia": alvo.get("estrategia", "desconhecida"),
        "indice_item": alvo.get("indice_item", -1),
        "trecho_item": (alvo.get("texto_item", "") or "")[:220],
        "screenshots": {"pre": pre_path, "post": post_path},
        "element_from_point": elem_info,
        "requests_captured": requests_captured,
        "request_captured": first_req,
        "clicked_via_js": clicked_via_js,
        "candidate_clicked": candidate_clicked,
    }


def clicar_com_retry_inteligente(page, id_alvo, max_tentativas=3, delay_entre_ms=800):
    ultima_excecao = None

    for tentativa in range(1, max_tentativas + 1):
        logger.info("clicar_com_retry_inteligente: tentativa %d/%d para ID %s", tentativa, max_tentativas, id_alvo)
        try:
            dados_clique = clicar_id_com_mouse(page, id_alvo)

            confirmou, estado_viz = aguardar_id_ativo_no_visualizador(page, id_alvo)
            if confirmou:
                logger.info("clicar_com_retry_inteligente: confirmacao recebida na tentativa %d para ID %s", tentativa, id_alvo)
                return dados_clique, estado_viz, tentativa

            logger.warning(
                "clicar_com_retry_inteligente: sem confirmacao apos clique na tentativa %d para ID %s. estado_viz=%s",
                tentativa, id_alvo, estado_viz,
            )
            if tentativa < max_tentativas:
                page.wait_for_timeout(delay_entre_ms)

        except Exception as e:
            ultima_excecao = e
            logger.exception("clicar_com_retry_inteligente: excecao na tentativa %d para ID %s: %s", tentativa, id_alvo, e)
            if tentativa < max_tentativas:
                page.wait_for_timeout(delay_entre_ms)

    logger.error("clicar_com_retry_inteligente: falhou apos %d tentativas para ID %s", max_tentativas, id_alvo)
    try:
        confirmou_final, estado_final = aguardar_id_ativo_no_visualizador(page, id_alvo, timeout_ms=3000, intervalo_ms=200)
    except Exception:
        estado_final = {"error": "falha ao coletar estado final"}

    raise RuntimeError(
        f"Clique no ID {id_alvo} falhou após {max_tentativas} tentativas. "
        f"Último erro: {str(ultima_excecao)}. Estado final: {estado_final}"
    )