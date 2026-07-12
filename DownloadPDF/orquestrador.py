from download_pdf import clicar_e_baixar, garantir_pasta_processo
from navegador import conectar_pagina


BASE_DIRETORIO_PROCESSOS = "/home/gabriel/Área de trabalho/N8N/variaveis/BAIXAR ARQUIVOS"


def executar_download(playwright, numero_processo, cdp_url, nome_base="documento", id_documento=""):
    pasta_destino = garantir_pasta_processo(BASE_DIRETORIO_PROCESSOS, numero_processo)
    browser, pagina = conectar_pagina(playwright, cdp_url)

    resultado = clicar_e_baixar(
        pagina,
        pasta_destino,
        nome_base=nome_base,
        id_documento=id_documento,
    )
    resultado["numero_processo"] = numero_processo
    resultado["id_documento"] = id_documento
    resultado["pasta_destino"] = pasta_destino
    resultado["titulo_pagina"] = pagina.title()
    resultado["url_pagina"] = pagina.url

    return resultado
