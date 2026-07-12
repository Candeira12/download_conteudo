import os
import re
import time
import urllib.parse
import urllib.request
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


DOWNLOAD_SELECTOR = "#download"


def garantir_pasta_processo(base_dir, numero_processo):
    pasta = os.path.join(base_dir, numero_processo)
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _extensao_por_content_type(content_type):
    ct = (content_type or "").lower()
    if "application/pdf" in ct:
        return ".pdf"
    if "text/html" in ct:
        return ".html"
    if "application/json" in ct:
        return ".json"
    return ".bin"


def _extrair_nome_por_headers(headers, fallback_name):
    content_disposition = headers.get("content-disposition", "") or ""

    m_star = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.IGNORECASE)
    if m_star:
        return m_star.group(1).strip().strip('"')

    m = re.search(r"filename=\"?([^\";]+)\"?", content_disposition, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return fallback_name


def _normalizar_nome_arquivo(nome):
    nome = (nome or "").strip()
    nome = re.sub(r"[\\/:*?\"<>|]", "_", nome)
    nome = nome.replace("..", ".")
    return nome or "download"


def _nome_final_com_id(nome_original, id_documento, extensao_padrao=".pdf"):
    id_limpo = _normalizar_nome_arquivo(id_documento)
    if not id_documento or not id_documento.strip():
        return _normalizar_nome_arquivo(nome_original)

    nome_original_limpo = _normalizar_nome_arquivo(nome_original)
    _, ext = os.path.splitext(nome_original_limpo)
    if not ext:
        ext = extensao_padrao

    return f"{id_limpo}{ext}"


def _gerar_caminho_unico(pasta_destino, nome_arquivo):
    nome_limpo = _normalizar_nome_arquivo(nome_arquivo)
    base, ext = os.path.splitext(nome_limpo)
    caminho = os.path.join(pasta_destino, nome_limpo)
    i = 1

    while os.path.exists(caminho):
        caminho = os.path.join(pasta_destino, f"{base}_{i}{ext}")
        i += 1

    return caminho


def _capturar_resposta_download(page, timeout_ms=20000):
    capturado = {"response": None}

    def on_response(response):
        if capturado["response"] is not None:
            return

        try:
            url = (response.url or "").lower()
            headers = response.headers or {}
            content_type = (headers.get("content-type", "") or "").lower()
            content_disposition = (headers.get("content-disposition", "") or "").lower()

            parece_download = (
                "attachment" in content_disposition
                or "/download/" in url
                or "application/pdf" in content_type
                or "application/octet-stream" in content_type
            )

            if parece_download:
                body = response.body()
                if body:
                    capturado["response"] = response
        except Exception:
            return

    page.on("response", on_response)

    try:
        inicio = time.time()
        while (time.time() - inicio) * 1000 < timeout_ms:
            if capturado["response"] is not None:
                return capturado["response"]
            page.wait_for_timeout(200)

        return None
    finally:
        page.remove_listener("response", on_response)


def _encontrar_frame_com_botao_download(page):
    try:
        if page.locator(DOWNLOAD_SELECTOR).count() > 0:
            return page
    except Exception:
        pass

    for frame in page.frames:
        try:
            if frame.locator(DOWNLOAD_SELECTOR).count() > 0:
                return frame
        except Exception:
            continue

    return None


def _obter_url_pdf_do_viewer(page, frame):
    viewer_url = ""
    if hasattr(frame, "url"):
        viewer_url = frame.url or ""

    if not viewer_url:
        viewer_url = page.url or ""

    parsed = urllib.parse.urlparse(viewer_url)
    params = urllib.parse.parse_qs(parsed.query)
    file_param = (params.get("file") or [""])[0]
    if not file_param:
        return ""

    file_param = urllib.parse.unquote(file_param)
    return urllib.parse.urljoin(page.url, file_param)


def _baixar_via_url_pdf_autenticada(
    page,
    frame,
    pasta_destino,
    nome_base,
    id_documento="",
    timeout_ms=25000,
):
    url_pdf = _obter_url_pdf_do_viewer(page, frame)
    if not url_pdf:
        raise RuntimeError("Nao foi possivel extrair URL do PDF a partir do viewer.")

    cookies = page.context.cookies([url_pdf])
    cookie_header = "; ".join(
        f"{c.get('name', '')}={c.get('value', '')}" for c in cookies if c.get("name")
    )

    request = urllib.request.Request(url_pdf, method="GET")
    request.add_header("User-Agent", page.evaluate("() => navigator.userAgent"))
    request.add_header("Accept", "application/pdf,application/octet-stream,*/*")
    if cookie_header:
        request.add_header("Cookie", cookie_header)

    with urllib.request.urlopen(request, timeout=max(5, int(timeout_ms / 1000))) as response:
        body = response.read()
        headers = {k.lower(): v for (k, v) in response.getheaders()}
        content_type = headers.get("content-type", "")

        fallback_nome = f"{nome_base}.pdf"
        nome_url = os.path.basename(urlparse(response.geturl() or url_pdf).path or "") or fallback_nome
        nome_final = _extrair_nome_por_headers(headers, nome_url)

        if "." not in os.path.basename(nome_final):
            nome_final = f"{nome_final}.pdf"

        nome_final = _nome_final_com_id(nome_final, id_documento, extensao_padrao=".pdf")

        caminho_arquivo = _gerar_caminho_unico(pasta_destino, nome_final)
        with open(caminho_arquivo, "wb") as f:
            f.write(body)

        return {
            "status": "sucesso",
            "fonte": "fallback_pdf_url",
            "caminho_arquivo": caminho_arquivo,
            "nome_arquivo": os.path.basename(caminho_arquivo),
            "url_download": response.geturl() or url_pdf,
            "content_type": content_type,
        }


def clicar_e_baixar(page, pasta_destino, nome_base="documento", id_documento="", timeout_ms=25000):
    alvo = _encontrar_frame_com_botao_download(page)
    if alvo is None:
        raise RuntimeError("Elemento de download do PDF nao encontrado: button#download")

    locator = alvo.locator(DOWNLOAD_SELECTOR).first
    if locator.count() == 0:
        raise RuntimeError("Elemento de download do PDF nao encontrado: button#download")

    locator.scroll_into_view_if_needed(timeout=5000)

    resposta_download = None
    download_event = None

    try:
        with page.expect_event("download", timeout=7000) as event_info:
            locator.click(timeout=5000)
        download_event = event_info.value
    except PlaywrightTimeoutError:
        # Em alguns cenarios via CDP, o evento download nao chega ao Playwright.
        # O clique ja foi executado dentro do expect_event.
        pass

    if download_event is not None:
        suggested = _normalizar_nome_arquivo(download_event.suggested_filename or f"{nome_base}.pdf")
        suggested = _nome_final_com_id(suggested, id_documento, extensao_padrao=".pdf")
        caminho_arquivo = _gerar_caminho_unico(pasta_destino, suggested)
        download_event.save_as(caminho_arquivo)
        return {
            "status": "sucesso",
            "fonte": "evento_download",
            "caminho_arquivo": caminho_arquivo,
            "nome_arquivo": os.path.basename(caminho_arquivo),
        }

    resposta_download = _capturar_resposta_download(page, timeout_ms=timeout_ms)
    if resposta_download is None:
        return _baixar_via_url_pdf_autenticada(
            page,
            alvo,
            pasta_destino,
            nome_base,
            id_documento=id_documento,
            timeout_ms=timeout_ms,
        )

    headers = resposta_download.headers or {}
    body = resposta_download.body()
    content_type = headers.get("content-type", "")

    parsed = urlparse(resposta_download.url or "")
    fallback_nome = f"{nome_base}{_extensao_por_content_type(content_type)}"
    nome_url = os.path.basename(parsed.path or "") or fallback_nome
    nome_final = _extrair_nome_por_headers(headers, nome_url)

    if "." not in os.path.basename(nome_final):
        nome_final = f"{nome_final}{_extensao_por_content_type(content_type)}"

    nome_final = _nome_final_com_id(
        nome_final,
        id_documento,
        extensao_padrao=_extensao_por_content_type(content_type),
    )

    caminho_arquivo = _gerar_caminho_unico(pasta_destino, nome_final)
    with open(caminho_arquivo, "wb") as f:
        f.write(body)

    return {
        "status": "sucesso",
        "fonte": "response_capture",
        "caminho_arquivo": caminho_arquivo,
        "nome_arquivo": os.path.basename(caminho_arquivo),
        "url_download": resposta_download.url,
        "content_type": content_type,
    }
