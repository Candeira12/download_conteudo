from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


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


def conectar_pagina(playwright, cdp_url):
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    pagina = selecionar_pagina_timeline(browser)

    if pagina is None:
        raise RuntimeError("Nenhuma aba valida foi encontrada no navegador conectado.")

    try:
        pagina.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        # Mesmo sem load state completo, tentamos continuar para inspecionar o DOM atual.
        pass

    return browser, pagina
