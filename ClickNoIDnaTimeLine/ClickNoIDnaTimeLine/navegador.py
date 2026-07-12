from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
import logging

logger = logging.getLogger(__name__)


def selecionar_pagina_timeline(browser):
    for contexto in browser.contexts:
        for pagina in contexto.pages:
            try:
                if pagina.locator(".timeline").count() > 0:
                    return pagina
            except Exception:
                continue

    if browser.contexts and browser.contexts[0].pages:
        return browser.contexts[0].pages[0]

    return None


def conectar_pagina_timeline(playwright, cdp_url):
    logger.debug("conectar_pagina_timeline: conectando a %s", cdp_url)
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    pagina = selecionar_pagina_timeline(browser)

    if pagina is None:
        raise RuntimeError("Nenhuma aba com timeline foi encontrada no navegador conectado.")

    try:
        pagina.wait_for_selector(".timeline", timeout=15000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("A timeline nao ficou disponivel na pagina dentro do tempo limite.") from exc

    return browser, pagina