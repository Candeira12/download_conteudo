import time
import logging

logger = logging.getLogger(__name__)


def salvar_screenshot_path(page, prefix):
    """
    Tenta salvar screenshot e retorna o path ou None.
    """
    path = None
    try:
        path = f"/tmp/{prefix}_{int(time.time())}.png"
        page.screenshot(path=path, full_page=False)
        logger.debug("salvar_screenshot_path: screenshot salvo em %s", path)
    except Exception:
        logger.exception("salvar_screenshot_path: falha ao salvar screenshot %s", prefix)
        path = None
    return path