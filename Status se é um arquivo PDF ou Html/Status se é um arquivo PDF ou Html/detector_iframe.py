def _normalizar_tipo(valor):
    texto = (valor or "").strip().lower()
    if not texto:
        return "desconhecido"

    if "pdfjs/web/viewer.html" in texto and "file=" in texto:
        return "pdf"

    if "pdf" in texto or texto.endswith(".pdf"):
        return "pdf"

    if "html" in texto or texto.startswith("text/"):
        return "html"

    return "desconhecido"


def obter_detalhes_iframe_ativo(page):
    dados = page.evaluate(
        """() => {
            const elementoAtivo = document.activeElement;
            const ehIframeAtivo = elementoAtivo && (
                elementoAtivo.tagName === 'IFRAME' || elementoAtivo.tagName === 'FRAME'
            );

            const elementos = Array.from(document.querySelectorAll('iframe, frame'));
            let iframeEscolhido = null;

            if (ehIframeAtivo) {
                iframeEscolhido = elementoAtivo;
            } else {
                iframeEscolhido = elementos.find((el) => {
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }) || null;
            }

            if (!iframeEscolhido) {
                return {
                    encontrado: false,
                    motivo: 'Nenhum iframe/frame foi encontrado na pagina.'
                };
            }

            const ret = iframeEscolhido.getBoundingClientRect();
            return {
                encontrado: true,
                ativo_pelo_focus: Boolean(ehIframeAtivo),
                src: iframeEscolhido.getAttribute('src') || '',
                id: iframeEscolhido.id || '',
                name: iframeEscolhido.getAttribute('name') || '',
                class_name: iframeEscolhido.className || '',
                largura: Math.round(ret.width),
                altura: Math.round(ret.height)
            };
        }"""
    )

    if not dados.get("encontrado"):
        return {
            "status": "erro",
            "tipo_conteudo": "desconhecido",
            "mensagem": dados.get("motivo", "Nao foi possivel localizar iframe ativo."),
        }

    frame = None
    seletor = ""

    if dados.get("id"):
        seletor = f"iframe#{dados['id']}, frame#{dados['id']}"
    elif dados.get("name"):
        nome = dados["name"].replace('"', '\\"')
        seletor = f'iframe[name="{nome}"], frame[name="{nome}"]'

    if seletor:
        handle = page.query_selector(seletor)
        if handle is not None:
            frame = handle.content_frame()

    tipo_detectado = _normalizar_tipo(dados.get("src", ""))
    frame_url = ""
    content_type = ""

    if frame is not None:
        frame_url = frame.url or ""
        tipo_detectado = _normalizar_tipo(frame_url) if tipo_detectado == "desconhecido" else tipo_detectado

        try:
            info_frame = frame.evaluate(
                """() => ({
                    contentType: document.contentType || '',
                    url: window.location.href || ''
                })"""
            )
            content_type = (info_frame or {}).get("contentType", "")
            url_interna = (info_frame or {}).get("url", "")

            tipo_por_content = _normalizar_tipo(content_type)
            # Content-Type do documento interno tem prioridade,
            # exceto quando a URL for explicitamente do viewer de PDF.js.
            if (
                tipo_por_content != "desconhecido"
                and "pdfjs/web/viewer.html" not in (frame_url or "").lower()
                and "pdfjs/web/viewer.html" not in (dados.get("src", "") or "").lower()
            ):
                tipo_detectado = tipo_por_content
            elif tipo_detectado != "pdf" and tipo_por_content != "desconhecido":
                tipo_detectado = tipo_por_content

            if not frame_url and url_interna:
                frame_url = url_interna
            if tipo_detectado == "desconhecido" and url_interna:
                tipo_detectado = _normalizar_tipo(url_interna)
        except Exception:
            pass

    if tipo_detectado == "desconhecido":
        tipo_detectado = "html"

    return {
        "status": "sucesso",
        "tipo_conteudo": tipo_detectado,
        "mensagem": "Iframe identificado com sucesso.",
        "iframe": {
            "src": dados.get("src", ""),
            "id": dados.get("id", ""),
            "name": dados.get("name", ""),
            "class_name": dados.get("class_name", ""),
            "ativo_pelo_focus": dados.get("ativo_pelo_focus", False),
            "largura": dados.get("largura", 0),
            "altura": dados.get("altura", 0),
            "frame_url": frame_url,
            "content_type": content_type,
        },
    }
