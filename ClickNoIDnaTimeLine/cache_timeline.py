import json
import os
import logging
import hashlib

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "timeline_clicker")
CACHE_FILE = os.path.join(CACHE_DIR, "timeline_patterns.json")


def garantir_diretorio_cache():
    """Garante que o diretório de cache existe."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def calcular_hash_pagina(page_url: str) -> str:
    """Calcula hash da URL para identificar diferentes páginas."""
    return hashlib.md5(page_url.encode()).hexdigest()[:8]


def carregar_patterns_cache(page_url: str) -> dict:
    """Carrega patterns e estratégias conhecidas para esta URL."""
    garantir_diretorio_cache()
    
    if not os.path.exists(CACHE_FILE):
        return {}
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_geral = json.load(f)
        
        hash_pagina = calcular_hash_pagina(page_url)
        patterns = cache_geral.get(hash_pagina, {})
        
        if patterns:
            logger.debug(f"✓ Patterns carregados para {hash_pagina}: {patterns}")
        return patterns
    except Exception as e:
        logger.exception("Erro ao carregar patterns do cache")
        return {}


def salvar_patterns_cache(page_url: str, patterns: dict):
    """Salva patterns de análise para esta URL."""
    garantir_diretorio_cache()
    
    try:
        hash_pagina = calcular_hash_pagina(page_url)
        
        # Carrega cache geral existente
        cache_geral = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_geral = json.load(f)
        
        # Atualiza patterns para esta página
        cache_geral[hash_pagina] = patterns
        
        # Salva arquivo
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_geral, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"✓ Patterns salvos para {hash_pagina}: {patterns}")
    except Exception as e:
        logger.exception("Erro ao salvar patterns no cache")


def analisar_estructura_timeline(page) -> dict:
    """
    Analisa estrutura do DOM uma única vez para descobrir:
    - Quais seletores CSS existem
    - Onde estão elementos clicáveis
    - Padrões de markup
    
    Retorna padrões que podem ser reutilizados.
    """
    try:
        patterns = page.evaluate(
            r"""() => {
            const itens = Array.from(document.querySelectorAll('.timeline .media'));
            
            if (itens.length === 0) {
                return { error: 'Nenhum item .timeline .media encontrado' };
            }
            
            // Analisa primeiros itens para descobrir estrutura
            const estrutura = {
                total_itens: itens.length,
                tem_links: false,
                tem_buttons: false,
                tem_ui_commandlink: false,
                tem_role_button: false,
                tem_onclick: false,
                tem_anchors_diretos: false,
                padroes_de_id: [],
            };
            
            // Examina até 10 itens para descobrir padrões
            for (let i = 0; i < Math.min(10, itens.length); i++) {
                const item = itens[i];
                const texto = (item.innerText || '').slice(0, 500);
                
                // Detecta elementos clicáveis
                if (item.querySelector('a')) estrutura.tem_links = true;
                if (item.querySelector('button')) estrutura.tem_buttons = true;
                if (item.querySelector('.ui-commandlink')) estrutura.tem_ui_commandlink = true;
                if (item.querySelector('[role="button"]')) estrutura.tem_role_button = true;
                if (item.querySelector('[onclick]')) estrutura.tem_onclick = true;
                
                // Links diretos dentro do item
                const anchors = Array.from(item.querySelectorAll('a'));
                if (anchors.length > 0 && anchors.some(a => a.getAttribute('href') && a.getAttribute('href').includes('/documento'))) {
                    estrutura.tem_anchors_diretos = true;
                }
                
                // Tenta extrair padrão de ID (números/caracteres especiais)
                const match = texto.match(/([A-Z0-9]{3,})/);
                if (match && !estrutura.padroes_de_id.includes(match[0])) {
                    estrutura.padroes_de_id.push(match[0].slice(0, 10));
                }
            }
            
            return estrutura;
            }"""
        )
        
        logger.info(f"Estrutura analisada: {patterns}")
        return patterns
    
    except Exception as e:
        logger.exception("Erro ao analisar estructura da timeline")
        return {}


def construir_seletores_otimizados(patterns: dict) -> dict:
    """
    Com base nos patterns descobertos, constrói seletores CSS otimizados
    que serão reutilizados nas próximas buscas.
    """
    seletores = {
        'item_base': '.timeline .media',
        'elementos_clicaveis': [],
    }
    
    # Monta ordem de prioridade de seletores clicáveis
    if patterns.get('tem_anchors_diretos'):
        seletores['elementos_clicaveis'].append('a[href*="/documento"]')
    if patterns.get('tem_links'):
        seletores['elementos_clicaveis'].append('a')
    if patterns.get('tem_ui_commandlink'):
        seletores['elementos_clicaveis'].append('.ui-commandlink')
    if patterns.get('tem_buttons'):
        seletores['elementos_clicaveis'].append('button')
    if patterns.get('tem_role_button'):
        seletores['elementos_clicaveis'].append('[role="button"]')
    if patterns.get('tem_onclick'):
        seletores['elementos_clicaveis'].append('[onclick]')
    
    # Fallback universal
    if not seletores['elementos_clicaveis']:
        seletores['elementos_clicaveis'] = ['a', 'button', '[onclick]', '.ui-commandlink']
    
    logger.debug(f"Seletores otimizados: {seletores}")
    return seletores


def limpar_cache():
    """Remove arquivo de cache."""
    garantir_diretorio_cache()
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
            logger.info(f"✓ Cache removido: {CACHE_FILE}")
        except Exception as e:
            logger.exception("Erro ao remover cache")