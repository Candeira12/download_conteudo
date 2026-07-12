import logging

logger = logging.getLogger(__name__)


def _coletar_sinais_visualizador(page):
    try:
        return page.evaluate(
            """() => {
                const frame = document.querySelector('iframe#framePdf, iframe[name="framePdf"], iframe, frame');
                const srcIframe = frame ? (frame.getAttribute('src') || '') : '';
                const ativoTag = document.activeElement ? document.activeElement.tagName : '';
                const ativoId = document.activeElement ? (document.activeElement.id || '') : '';

                const objeto = document.querySelector('object[data], embed[src]');
                const srcObj = objeto ? (objeto.getAttribute('data') || objeto.getAttribute('src') || '') : '';

                return {
                    src_iframe: srcIframe,
                    src_objeto: srcObj,
                    tag_ativo: ativoTag,
                    id_ativo: ativoId,
                    href: window.location.href || '',
                };
            }"""
        )
    except Exception:
        logger.exception("_coletar_sinais_visualizador: falha ao executar evaluate")
        return {"src_iframe": "", "src_objeto": "", "tag_ativo": "", "id_ativo": "", "href": getattr(page, "url", "")}


def _monitorar_visualizador_com_deteccao(page, id_alvo, timeout_ms=30000, intervalo_ms=200):
    id_limpo = (id_alvo or "").strip()
    if not id_limpo:
        return False, _coletar_sinais_visualizador(page)

    try:
        page.evaluate("""() => {
            window.__dom_observer = { mudancas_detectadas: false };
            const observer = new MutationObserver(() => { window.__dom_observer.mudancas_detectadas = true; });
            observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['src','data','href'] });
        }""")
    except Exception:
        logger.exception("_monitorar_visualizador_com_deteccao: falha ao injetar observer")

    tentativas = max(1, int(timeout_ms / intervalo_ms))
    ultimo_estado = {}

    for tentativa in range(tentativas):
        estado = _coletar_sinais_visualizador(page)
        ultimo_estado = estado
        logger.debug("_monitorar_visualizador: tentativa %d/%d estado=%s", tentativa + 1, tentativas, estado)

        campos_criticos = [
            ("src_iframe", estado.get("src_iframe", "")),
            ("src_objeto", estado.get("src_objeto", "")),
            ("href", estado.get("href", "")),
            ("id_ativo", estado.get("id_ativo", "")),
        ]

        encontrado = False
        campo_encontrado = None
        for nome_campo, valor in campos_criticos:
            if id_limpo in (valor or ""):
                encontrado = True
                campo_encontrado = nome_campo
                break

        # Adiciona criterio: aceitar viewer.html (pdf.js) ou /documento/download/
        if not encontrado:
            si = (estado.get("src_iframe") or "") or ""
            href = (estado.get("href") or "") or ""
            if 'viewer.html' in si or '/documento/download/' in si or '/documento/download/' in href:
                encontrado = True
                campo_encontrado = 'viewer_or_download'

        if encontrado:
            logger.info("_monitorar_visualizador: criterio de sucesso detectado (%s) na tentativa %d", campo_encontrado, tentativa + 1)
            page.wait_for_timeout(intervalo_ms)
            estado_confirm = _coletar_sinais_visualizador(page)
            # se o id aparecer especificamente, retorna confirmação com campo exato
            for nome_campo, _ in campos_criticos:
                if id_limpo in (estado_confirm.get(nome_campo, "") or ""):
                    return True, {**estado_confirm, "campo_confirmacao": nome_campo, "tentativa": tentativa + 1}
            # caso contrario, retorna confirmacao por viewer_or_download
            return True, {**estado_confirm, "campo_confirmacao": campo_encontrado, "tentativa": tentativa + 1}

        page.wait_for_timeout(intervalo_ms)

    logger.warning("_monitorar_visualizador: nao detectou ID %s apos %d tentativas. ultimo_estado=%s", id_alvo, tentativas, ultimo_estado)
    return False, ultimo_estado


def aguardar_id_ativo_no_visualizador(page, id_alvo, timeout_ms=30000, intervalo_ms=200):
    logger = logging.getLogger(__name__)
    logger.debug("aguardar_id_ativo_no_visualizador: aguardando ID %s (timeout %d ms)", id_alvo, timeout_ms)
    confirmou, estado = _monitorar_visualizador_com_deteccao(page, id_alvo, timeout_ms=timeout_ms, intervalo_ms=intervalo_ms)
    logger.debug("aguardar_id_ativo_no_visualizador: resultado confirmou=%s estado=%s", confirmou, estado)
    return confirmou, estado