#!/home/gabriel/.venv/bin/python3
import json
import os
import sys

from playwright.sync_api import sync_playwright

from orquestrador import executar_extracao


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(
            json.dumps(
                {
                    "status": "erro",
                    "mensagem": "Informe o numero do processo. Uso: python3 main.py <numero_processo> <id_documento> [seletor] [--corpo]",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    numero_processo = sys.argv[1].strip()
    id_documento = ""
    seletor = "table"  # Seletor padrão
    usar_corpo_pagina = False

    # Argumentos opcionais
    if len(sys.argv) > 2 and sys.argv[2].strip():
        id_documento = sys.argv[2].strip()

    if len(sys.argv) > 3 and sys.argv[3].strip():
        arg = sys.argv[3].strip()
        if arg == "--corpo":
            usar_corpo_pagina = True
        else:
            seletor = arg

    # Flag para usar corpo da página
    if len(sys.argv) > 4 and sys.argv[4].strip() == "--corpo":
        usar_corpo_pagina = True

    cdp_url = os.getenv("CDP_URL", "http://localhost:9222")

    try:
        with sync_playwright() as playwright:
            resultado = executar_extracao(
                playwright=playwright,
                numero_processo=numero_processo,
                cdp_url=cdp_url,
                id_documento=id_documento,
                seletor=seletor,
                usar_corpo_pagina=usar_corpo_pagina,
            )

        print(json.dumps(resultado, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "erro",
                    "numero_processo": numero_processo,
                    "id_documento": id_documento,
                    "mensagem": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())