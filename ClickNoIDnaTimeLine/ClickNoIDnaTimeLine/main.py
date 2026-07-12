#!/home/gabriel/.venv/bin/python3
import json
import os
import sys
import logging
from playwright.sync_api import sync_playwright

from clique_timeline import executar_clique_no_id


def ler_id_entrada(argv):
    if len(argv) > 1 and argv[1].strip():
        return argv[1].strip()

    id_env = os.getenv("ID_TIMELINE", "").strip()
    if id_env:
        return id_env

    return ""


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "DEBUG"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")

    id_alvo = ler_id_entrada(sys.argv)
    if not id_alvo:
        logger.error("ID nao informado. Uso: python3 main.py <id>")
        print(
            json.dumps(
                {
                    "status": "erro",
                    "mensagem": "ID nao informado. Uso: python3 main.py <id>",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    cdp_url = os.getenv("CDP_URL", "http://localhost:9222")

    try:
        with sync_playwright() as playwright:
            resultado = executar_clique_no_id(playwright, id_alvo, cdp_url)

        print(json.dumps(resultado, ensure_ascii=False))
        return 0
    except Exception as exc:
        logger.exception("Erro ao executar clique no ID %s", id_alvo)
        print(
            json.dumps(
                {
                    "status": "erro",
                    "id": id_alvo,
                    "mensagem": str(exc),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())