from detector_iframe import obter_detalhes_iframe_ativo
from navegador import conectar_pagina


def executar_verificacao(playwright, cdp_url):
    browser, pagina = conectar_pagina(playwright, cdp_url)

    resultado = obter_detalhes_iframe_ativo(pagina)
    resultado["titulo_pagina"] = pagina.title()
    resultado["url_pagina"] = pagina.url

    return resultado
