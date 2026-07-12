import os
import re
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def garantir_pasta_processo(base_dir, numero_processo):
    """Garante que a pasta do processo existe."""
    pasta = os.path.join(base_dir, numero_processo)
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _normalizar_nome_arquivo(nome):
    """Remove caracteres inválidos do nome do arquivo."""
    nome = (nome or "").strip()
    nome = re.sub(r"[\\/:*?\"<>|]", "_", nome)
    nome = nome.replace("..", ".")
    return nome or "texto"


def _gerar_caminho_unico(pasta_destino, nome_arquivo):
    """Gera um caminho único para o arquivo, evitando sobrescrita."""
    nome_limpo = _normalizar_nome_arquivo(nome_arquivo)
    base, ext = os.path.splitext(nome_limpo)
    caminho = os.path.join(pasta_destino, nome_limpo)
    i = 1

    while os.path.exists(caminho):
        caminho = os.path.join(pasta_destino, f"{base}_{i}{ext}")
        i += 1

    return caminho


def _encontrar_iframe(page):
    """Encontra o primeiro iframe disponível na página."""
    try:
        frames = page.frames
        if len(frames) > 1:  # Primeiro frame é a página principal
            return frames[1]
    except Exception:
        pass
    return None


def _extrair_textos_de_elementos(frame, seletor="body"):
    """Extrai textos de elementos dentro do iframe."""
    if frame is None:
        return []

    try:
        # Se seletor é "table", extrai texto das linhas de tabela
        if seletor.lower() == "table":
            tabelas = frame.locator("table").all()
            textos = []
            for tabela in tabelas:
                texto = tabela.text_content()
                if texto and texto.strip():
                    textos.append(texto.strip())
            return textos
        
        # Para seletores genéricos
        elementos = frame.locator(seletor).all()
        textos = []

        for elemento in elementos:
            try:
                texto = elemento.text_content()
                if texto and texto.strip():
                    textos.append(texto.strip())
            except Exception:
                continue

        return textos
    except Exception as e:
        print(f"Erro ao extrair textos: {e}", file=__import__('sys').stderr)
        return []


def _extrair_texto_corpo_pagina(page):
    """Extrai o texto completo do corpo da página (não iframe)."""
    try:
        body = page.locator("body").first
        if body:
            texto = body.text_content()
            if texto and texto.strip():
                return [texto.strip()]
    except Exception:
        pass
    return []


def _consolidar_textos(textos, separador="\n\n"):
    """Consolida os textos extraídos em um único string."""
    if not textos:
        return ""
    
    # Remove textos duplicados preservando ordem
    textos_unicos = []
    vistos = set()
    for texto in textos:
        if texto not in vistos:
            vistos.add(texto)
            textos_unicos.append(texto)
    
    return separador.join(textos_unicos)


def extrair_e_salvar_texto(
    page,
    pasta_destino,
    id_documento="",
    seletor="table",
    timeout_ms=15000,
    usar_corpo_pagina=False,
):
    """Extrai textos do iframe ou corpo da página e salva em arquivo."""
    
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass

    textos = []
    
    if usar_corpo_pagina:
        # Extrai do corpo da página inteira (não usa iframe)
        textos = _extrair_texto_corpo_pagina(page)
    else:
        # Encontra o iframe
        iframe = _encontrar_iframe(page)
        if iframe is None:
            raise RuntimeError("Nenhum iframe encontrado na página.")

        # Extrai textos dos elementos
        textos = _extrair_textos_de_elementos(iframe, seletor)
    
    if not textos:
        raise RuntimeError(f"Nenhum texto encontrado usando o seletor '{seletor}' na página.")

    # Consolida os textos
    conteudo_final = _consolidar_textos(textos)

    # Define o nome do arquivo
    if id_documento and id_documento.strip():
        nome_arquivo = f"{_normalizar_nome_arquivo(id_documento)}.txt"
    else:
        nome_arquivo = "texto.txt"

    # Gera caminho único
    caminho_arquivo = _gerar_caminho_unico(pasta_destino, nome_arquivo)

    # Salva o arquivo
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write(conteudo_final)

    return {
        "status": "sucesso",
        "caminho_arquivo": caminho_arquivo,
        "nome_arquivo": os.path.basename(caminho_arquivo),
        "quantidade_textos": len(textos),
        "tamanho_bytes": os.path.getsize(caminho_arquivo),
    }