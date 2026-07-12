import re
import logging
import sys
import os

# Adiciona parent directory ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache_timeline import (
    carregar_patterns_cache,
    salvar_patterns_cache,
    analisar_estructura_timeline,
    construir_seletores_otimizados,
)

logger = logging.getLogger(__name__)


def normalizar_texto(texto):
    return " ".join((texto or "").split())


def _id_em_texto(texto, id_alvo):
    if not texto or not id_alvo:
        return False
    return re.search(rf"(?<!\d){re.escape(id_alvo)}(?!\d)", texto) is not None


def obter_alvo_de_clique_por_id(page, id_alvo):
    """
    Retorna o melhor ponto/estrategia para clicar no item que contém id_alvo.
    
    PRIMEIRA VEZ (sem cache):
      1. Analisa estrutura da timeline (quais seletores funcionam)
      2. Salva patterns para reutilização
      3. Procura o ID com estratégia otimizada
    
    PRÓXIMAS VEZES (com cache):
      1. Carrega patterns conhecidos
      2. Usa seletores otimizados direto
      3. Procura o ID (muito mais rápido)
    
    Se não encontrar, refaz análise e atualiza cache.
    """
    id_limpo = normalizar_texto(id_alvo)
    if not id_limpo:
        raise ValueError("ID alvo vazio.")

    page_url = page.url
    
    # FASE 1: Tenta carregar patterns do cache
    logger.debug(f"Buscando patterns em cache para {page_url}")
    patterns = carregar_patterns_cache(page_url)
    
    if not patterns:
        logger.info("⏱️  Cache vazio → ANALISANDO estrutura da timeline...")
        patterns = analisar_estructura_timeline(page)
        if patterns and 'error' not in patterns:
            seletores = construir_seletores_otimizados(patterns)
            patterns['seletores'] = seletores
            salvar_patterns_cache(page_url, patterns)
            logger.info(f"✓ Patterns salvos para próximas buscas")
    
    # FASE 2: Usa patterns (se existirem) para buscar ID com estratégia otimizada
    seletores = patterns.get('seletores', {})
    
    try:
        dados = page.evaluate(
            r"""(args) => {
            const { idAlvo, seletoresOtimizados } = args;
            const regex = new RegExp(`(^|\\D)${idAlvo.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}(\\D|$)`);
            const itens = Array.from(document.querySelectorAll('.timeline .media'));

            for (let idx = 0; idx < itens.length; idx += 1) {
                const item = itens[idx];
                const texto = (item.innerText || '').replace(/\s+/g, ' ').trim();
                if (!texto || !regex.test(texto)) {
                    continue;
                }

                item.scrollIntoView({ block: 'center', inline: 'nearest' });

                // Tenta seletores otimizados primeiro
                const seletoresClique = seletoresOtimizados.elementos_clicaveis.length > 0
                    ? seletoresOtimizados.elementos_clicaveis
                    : ['a', 'button', '[role="button"], [onclick], .ui-commandlink'];
                
                for (const seletor of seletoresClique) {
                    const candidatos = Array.from(item.querySelectorAll(seletor));
                    for (const el of candidatos) {
                        const textoEl = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
                        if (!regex.test(textoEl)) {
                            continue;
                        }

                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            return {
                                encontrou: true,
                                estrategia: 'elemento-clicavel',
                                x: r.left + (r.width / 2),
                                y: r.top + (r.height / 2),
                                texto_item: texto,
                                indice_item: idx,
                            };
                        }
                    }
                }

                // Fallback: procura texto dentro do item
                const walker = document.createTreeWalker(item, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) {
                    const noTexto = walker.currentNode;
                    const valor = noTexto.nodeValue || '';
                    const pos = valor.search(new RegExp(`(?<!\\d)${idAlvo.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}(?!\\d)`));
                    if (pos < 0) {
                        continue;
                    }

                    const range = document.createRange();
                    range.setStart(noTexto, pos);
                    range.setEnd(noTexto, pos + idAlvo.length);
                    const rect = range.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            encontrou: true,
                            estrategia: 'faixa-texto-id',
                            x: rect.left + (rect.width / 2),
                            y: rect.top + (rect.height / 2),
                            texto_item: texto,
                            indice_item: idx,
                        };
                    }
                }

                // Fallback: centro do item
                const rItem = item.getBoundingClientRect();
                if (rItem.width > 0 && rItem.height > 0) {
                    return {
                        encontrou: true,
                        estrategia: 'centro-item',
                        x: rItem.left + (rItem.width / 2),
                        y: rItem.top + (rItem.height / 2),
                        texto_item: texto,
                        indice_item: idx,
                    };
                }
            }

            return {
                encontrou: false,
                mensagem: `ID ${idAlvo} nao foi encontrado em itens clicaveis da timeline.`,
            };
        }""",
            {"idAlvo": id_limpo, "seletoresOtimizados": seletores}
        )
        
        logger.debug(f"Resultado: {str(dados)[:500]}")
    except Exception as e:
        logger.exception("Erro ao executar busca otimizada")
        raise RuntimeError(f"Erro ao executar script para localizar alvo clicavel: {e}") from e

    if not dados or not dados.get("encontrou"):
        logger.error(f"ID não encontrado: {dados}")
        raise RuntimeError((dados or {}).get("mensagem", f"ID {id_limpo} nao encontrado."))

    return dados


def localizar_item_por_id(page, id_alvo):
    """Localiza o elemento DOM do item contendo id_alvo."""
    id_limpo = normalizar_texto(id_alvo)
    if not id_limpo:
        raise ValueError("ID alvo vazio.")

    logger.debug(f"Localizando item com ID: {id_limpo}")

    for item in page.query_selector_all(".timeline .media"):
        try:
            texto = normalizar_texto(item.inner_text() if item else "")
        except Exception:
            texto = ""
        if not texto:
            continue

        if _id_em_texto(texto, id_limpo):
            logger.debug(f"✓ Item encontrado")
            return item

    logger.debug(f"ID {id_limpo} nao encontrado")
    return None
