#!/home/gabriel/.venv/bin/python3
import json
import os
import sys

from playwright.sync_api import sync_playwright

from orquestrador import executar_verificacao


def main():
    cdp_url = os.getenv("CDP_URL", "http://localhost:9222")

    try:
        with sync_playwright() as playwright:
            resultado = executar_verificacao(playwright, cdp_url)

        print(json.dumps(resultado, ensure_ascii=False))
        return 0 if resultado.get("status") == "sucesso" else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "erro",
                    "tipo_conteudo": "desconhecido",
                    "mensagem": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
