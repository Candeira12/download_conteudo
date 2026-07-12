"""
Locator module - Finds clickable elements by ID in timeline items.
Handles DOM inspection with caching and multiple fallback strategies.
Also loads pre-computed element locations from cache for faster lookups.
"""
import re
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache_timeline import (
    carregar_patterns_cache,
    salvar_patterns_cache,
    analisar_estructura_timeline,
    construir_seletores_otimizados,
)

try:
    from cache_localizacoes import carregar_localizacoes, obter_documento_por_id
    CACHE_LOCALIZACOES_DISPONIVEL = True
except ImportError:
    CACHE_LOCALIZACOES_DISPONIVEL = False

logger = logging.getLogger(__name__)


def normalizar_texto(texto):
    """Normaliza whitespace em texto."""
    return " ".join((texto or "").split())


def _id_em_texto(texto, id_alvo):
    """Verifica se id_alvo aparece em texto como palavra inteira."""
    if not texto or not id_alvo:
        return False
    return re.search(rf"(?<!\d){re.escape(id_alvo)}(?!\d)", texto) is not None


def _obter_script_localizacao(id_alvo, seletores_otimizados):
    """
    Retorna o script JavaScript para localizar o elemento clicável.
    
    Args:
        id_alvo: ID a procurar
        seletores_otimizados: Dict com estratégia de seletores CSS
    
    Returns:
        Tupla (script_js, parametros_dict)
    """
    script = r"""
    (args) => {
        const { idAlvo, seletoresOtimizados } = args;
        
        // Valida entradas
        if (!idAlvo || typeof idAlvo !== 'string') {
            return { encontrou: false, mensagem: 'ID inválido' };
        }
        
        try {
            // Cria regex para busca de ID exato (não substring)
            const regexId = new RegExp(
                `(^|\\D)${idAlvo.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}(\\D|$)`
            );
            
            // Busca todos os itens da timeline
            const itens = Array.from(document.querySelectorAll('.timeline .media'));
            
            if (itens.length === 0) {
                return { encontrou: false, mensagem: 'Timeline não encontrada' };
            }
            
            // Processa cada item
            for (let idx = 0; idx < itens.length; idx++) {
                const item = itens[idx];
                const texto = (item.innerText || '').replace(/\s+/g, ' ').trim();
                
                // Verifica se o ID está no texto do item
                if (!texto || !regexId.test(texto)) {
                    continue;
                }
                
                // Scroll para o item
                item.scrollIntoView({ block: 'center', inline: 'nearest' });
                
                // Tenta encontrar elemento clicável dentro do item
                const resultado = _procurarElementoClicavel(item, idAlvo, regexId, texto, idx, seletoresOtimizados);
                if (resultado.encontrou) {
                    return resultado;
                }
            }
            
            return { encontrou: false, mensagem: `ID ${idAlvo} não encontrado` };
            
        } catch (erro) {
            return { encontrou: false, mensagem: `Erro: ${erro.message}` };
        }
    }
    
    // Função auxiliar para procurar elemento clicável
    function _procurarElementoClicavel(item, idAlvo, regexId, texto, idx, seletoresOtimizados) {
        // 1. Tenta seletores otimizados
        const selectores = (seletoresOtimizados.elementos_clicaveis || []).length > 0
            ? seletoresOtimizados.elementos_clicaveis
            : ['a', 'button', '[role="button"]', '[onclick]', '.ui-commandlink'];
        
        for (const seletor of selectores) {
            const candidatos = Array.from(item.querySelectorAll(seletor));
            for (const el of candidatos) {
                const textoEl = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
                if (!regexId.test(textoEl)) continue;
                
                const bbox = el.getBoundingClientRect();
                if (bbox.width > 0 && bbox.height > 0) {
                    return {
                        encontrou: true,
                        estrategia: 'elemento-clicavel',
                        x: bbox.left + (bbox.width / 2),
                        y: bbox.top + (bbox.height / 2),
                        texto_item: texto,
                        indice_item: idx,
                    };
                }
            }
        }
        
        // 2. Fallback: procura o texto do ID especificamente
        const walker = document.createTreeWalker(
            item,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        let nodeTexto;
        while ((nodeTexto = walker.nextNode())) {
            const valor = nodeTexto.nodeValue || '';
            const match = valor.match(
                new RegExp(`(?<!\\d)${idAlvo.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}(?!\\d)`)
            );
            
            if (match) {
                const range = document.createRange();
                range.setStart(nodeTexto, match.index);
                range.setEnd(nodeTexto, match.index + idAlvo.length);
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
        }
        
        // 3. Fallback: centro do item
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
        
        return { encontrou: false };
    }
    """
    
    params = {
        "idAlvo": id_alvo,
        "seletoresOtimizados": seletores_otimizados or {}
    }
    
    return script, params


def obter_alvo_de_clique_por_id(page, id_alvo, numero_processo=None):
    """
    Localiza o melhor ponto para clicar em um elemento contendo o ID.
    
    Usa cache para otimizar buscas subsequentes.
    Primeiro tenta usar cache de localizações pré-computadas, depois busca no DOM.
    """
    id_limpo = normalizar_texto(id_alvo)
    if not id_limpo:
        raise ValueError("ID alvo vazio.")
    
    # Tenta usar cache de localizações se disponível
    if CACHE_LOCALIZACOES_DISPONIVEL and numero_processo:
        try:
            doc_em_cache = obter_documento_por_id(numero_processo, id_limpo)
            if doc_em_cache:
                logger.info(f"✓ Localização encontrada no cache para ID {id_limpo}")
                return {
                    "encontrou": True,
                    "estrategia": "cache-localizacoes",
                    "indice_item": doc_em_cache.get("indice_item"),
                    "seletor_css": doc_em_cache.get("seletor_css"),
                    "texto_item": doc_em_cache.get("titulo", ""),
                    "dados_adicionais": doc_em_cache
                }
        except Exception as cache_error:
            logger.debug(f"Não foi possível usar cache: {cache_error}")
    
    page_url = page.url
    logger.debug(f"Localizando ID {id_limpo} em {page_url}")
    
    # Carrega patterns do cache
    patterns = carregar_patterns_cache(page_url)
    
    if not patterns:
        logger.info("Cache vazio → Analisando estrutura da timeline...")
        patterns = analisar_estructura_timeline(page)
        if patterns and 'error' not in patterns:
            seletores = construir_seletores_otimizados(patterns)
            patterns['seletores'] = seletores
            salvar_patterns_cache(page_url, patterns)
            logger.info("✓ Patterns salvos em cache")
    
    seletores = patterns.get('seletores', {})
    
    try:
        # Executa busca com API correta
        script, parametros = _obter_script_localizacao(id_limpo, seletores)
        dados = page.evaluate(script, parametros)
        
        logger.debug(f"Resultado: {str(dados)[:300]}")
    except Exception as e:
        logger.exception(f"Erro ao executar busca de ID: {e}")
        raise RuntimeError(f"Erro ao localizar elemento: {e}") from e
    
    if not dados or not dados.get("encontrou"):
        mensagem = dados.get("mensagem", f"ID {id_limpo} não encontrado")
        logger.error(f"ID não localizado: {mensagem}")
        raise RuntimeError(mensagem)
    
    return dados


def localizar_item_por_id(page, id_alvo, numero_processo=None):
    """
    Localiza o elemento DOM do item contendo o ID.
    Usa Playwright query_selector_all (alternativa mais simples).
    
    Se numero_processo for fornecido, tenta usar cache primeiro.
    """
    id_limpo = normalizar_texto(id_alvo)
    if not id_limpo:
        raise ValueError("ID alvo vazio.")
    
    logger.debug(f"Localizando item com ID: {id_limpo}")
    
    # Tenta usar cache de localizações se disponível
    if CACHE_LOCALIZACOES_DISPONIVEL and numero_processo:
        try:
            doc_em_cache = obter_documento_por_id(numero_processo, id_limpo)
            if doc_em_cache:
                indice = doc_em_cache.get("indice_item")
                if indice is not None:
                    itens = page.query_selector_all(".timeline .media")
                    if 0 <= indice < len(itens):
                        logger.info(f"✓ Item encontrado no cache (índice: {indice})")
                        return itens[indice]
        except Exception as cache_error:
            logger.debug(f"Não foi possível usar cache: {cache_error}")
    
    # Busca no DOM
    itens = page.query_selector_all(".timeline .media")
    for item in itens:
        try:
            texto = normalizar_texto(item.inner_text() or "")
        except Exception:
            texto = ""
        
        if texto and _id_em_texto(texto, id_limpo):
            logger.debug(f"✓ Item encontrado")
            return item
    
    logger.debug(f"ID {id_limpo} não encontrado")
    return None
