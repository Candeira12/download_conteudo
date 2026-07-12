from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


DOWNLOAD_SELECTOR = "#download"


def _pagina_tem_botao_download_pdf(pagina):
    try:
        if pagina.locator(DOWNLOAD_SELECTOR).count() > 0:
            return True
    except Exception:
        pass

    try:
        for frame in pagina.frames:
            try:
                if frame.locator(DOWNLOAD_SELECTOR).count() > 0:
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def selecionar_pagina_alvo(browser):
    # Prioriza a aba que contem o botao #download do viewer PDF.js.
    for contexto in browser.contexts:
        for pagina in contexto.pages:
            if _pagina_tem_botao_download_pdf(pagina):
                return pagina

    # Como fallback, pega a ultima aba da primeira janela assumindo que ela esta ativa.
    if browser.contexts and browser.contexts[0].pages:
        return browser.contexts[0].pages[-1]

    # Fallback secundario: alguma aba com timeline.
    for contexto in browser.contexts:
        for pagina in contexto.pages:
            try:
                if pagina.locator(".timeline").count() > 0:
                    return pagina
            except Exception:
                continue

    return None


def conectar_pagina(playwright, cdp_url):
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    pagina = selecionar_pagina_alvo(browser)
    if pagina is None:
        raise RuntimeError("Nenhuma aba valida encontrada no navegador conectado.")

    try:
        pagina.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        pass

    return browser, pagina
