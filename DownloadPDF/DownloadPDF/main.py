#!/home/gabriel/.venv/bin/python3
import json
import os
import sys

from playwright.sync_api import sync_playwright

from orquestrador import executar_download


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(
            json.dumps(
                {
                    "status": "erro",
                    "mensagem": "Informe o numero do processo. Uso: python3 main.py <numero_processo> [id_documento] ou python3 main.py <numero_processo> <nome_base> <id_documento>",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    numero_processo = sys.argv[1].strip()
    nome_base = "documento"
    id_documento = ""

    # Compatibilidade de chamada:
    # 1) main.py <processo> <id_documento>
    # 2) main.py <processo> <nome_base> <id_documento>
    if len(sys.argv) > 2 and sys.argv[2].strip():
        if len(sys.argv) > 3 and sys.argv[3].strip():
            nome_base = sys.argv[2].strip()
            id_documento = sys.argv[3].strip()
        else:
            id_documento = sys.argv[2].strip()

    cdp_url = os.getenv("CDP_URL", "http://localhost:9222")

    try:
        with sync_playwright() as playwright:
            resultado = executar_download(
                playwright=playwright,
                numero_processo=numero_processo,
                cdp_url=cdp_url,
                nome_base=nome_base,
                id_documento=id_documento,
            )

        print(json.dumps(resultado, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "erro",
                    "numero_processo": numero_processo,
                    "mensagem": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
