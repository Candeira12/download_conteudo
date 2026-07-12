#!/home/gabriel/.venv/bin/python3
import json
import os
import sys
import logging
from playwright.sync_api import sync_playwright

from clique_timeline import executar_clique_no_id
from cache_localizacoes import criar_lock_processo, liberar_lock_processo


def ler_entrada(argv):
    """Lê o número do processo e ID alvo dos argumentos ou variáveis de ambiente."""
    numero_processo = None
    id_alvo = None
    
    # Lê argumentos da linha de comando
    if len(argv) > 1:
        numero_processo = argv[1].strip() if argv[1].strip() else None
    if len(argv) > 2:
        id_alvo = argv[2].strip() if argv[2].strip() else None
    
    # Fallback para variáveis de ambiente
    if not numero_processo:
        numero_processo = os.getenv("NUMERO_PROCESSO", "").strip()
    if not id_alvo:
        id_alvo = os.getenv("ID_TIMELINE", "").strip()
    
    return numero_processo, id_alvo


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "DEBUG"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")

    numero_processo, id_alvo = ler_entrada(sys.argv)
    
    if not numero_processo:
        logger.error("Número do processo não informado.")
        print(
            json.dumps(
                {
                    "status": "erro",
                    "mensagem": "Número do processo não informado. Uso: python3 main.py <numero_processo> <id_alvo>",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    
    if not id_alvo:
        logger.error("ID alvo não informado.")
        print(
            json.dumps(
                {
                    "status": "erro",
                    "processo": numero_processo,
                    "mensagem": "ID alvo não informado. Uso: python3 main.py <numero_processo> <id_alvo>",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    cdp_url = os.getenv("CDP_URL", "http://localhost:9222")

    try:
        # Cria lock para indicar que o processo está em uso
        logger.info(f"Processando: processo={numero_processo}, id={id_alvo}")
        criar_lock_processo(numero_processo)
        
        try:
            with sync_playwright() as playwright:
                # Passa numero_processo para que o locator possa usar o cache
                resultado = executar_clique_no_id(
                    playwright, 
                    id_alvo, 
                    cdp_url,
                    numero_processo=numero_processo
                )

            print(json.dumps(resultado, ensure_ascii=False))
            return 0
        finally:
            # Sempre libera o lock ao terminar
            liberar_lock_processo(numero_processo)
            logger.info(f"Lock liberado para processo {numero_processo}")
            
    except Exception as exc:
        logger.exception("Erro ao executar clique no ID %s", id_alvo)
        print(
            json.dumps(
                {
                    "status": "erro",
                    "processo": numero_processo,
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
