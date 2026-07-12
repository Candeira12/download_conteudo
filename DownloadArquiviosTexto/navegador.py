from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def selecionar_pagina_alvo(browser):
    """Seleciona a página ativa no navegador."""
    # Prioriza a última aba da primeira janela assumindo que ela está ativa
    if browser.contexts and browser.contexts[0].pages:
        return browser.contexts[0].pages[-1]

    # Fallback: retorna qualquer aba disponível
    for contexto in browser.contexts:
        for pagina in contexto.pages:
            return pagina

    return None


def conectar_pagina(playwright, cdp_url):
    """Conecta ao navegador via CDP e retorna browser e página."""
    browser = playwright.chromium.connect_over_cdp(cdp_url)
    pagina = selecionar_pagina_alvo(browser)
    if pagina is None:
        raise RuntimeError("Nenhuma aba válida encontrada no navegador conectado.")

    try:
        pagina.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        pass

    return browser, pagina