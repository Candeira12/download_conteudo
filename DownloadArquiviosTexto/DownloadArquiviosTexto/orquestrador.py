from extrator_texto import extrair_e_salvar_texto, garantir_pasta_processo
from navegador import conectar_pagina


BASE_DIRETORIO_PROCESSOS = "/home/gabriel/Área de trabalho/N8N/variaveis/BAIXAR ARQUIVOS"


def executar_extracao(
    playwright,
    numero_processo,
    cdp_url,
    id_documento="",
    seletor="table",
    usar_corpo_pagina=False,
):
    """Orquestra a extração de texto do iframe."""
    pasta_destino = garantir_pasta_processo(BASE_DIRETORIO_PROCESSOS, numero_processo)
    browser, pagina = conectar_pagina(playwright, cdp_url)

    resultado = extrair_e_salvar_texto(
        pagina,
        pasta_destino,
        id_documento=id_documento,
        seletor=seletor,
        usar_corpo_pagina=usar_corpo_pagina,
    )
    resultado["numero_processo"] = numero_processo
    resultado["id_documento"] = id_documento
    resultado["pasta_destino"] = pasta_destino
    resultado["titulo_pagina"] = pagina.title()
    resultado["url_pagina"] = pagina.url

    return resultado