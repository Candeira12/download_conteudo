"""
Session Keeper - Mantém cookies e estado da sessão durante execução.

Este módulo previne a perda de cookies entre execuções do fluxo N8N,
salvando e restaurando cookies sem recarregar a página (F5).

Uso:
    from session_keeper import salvar_cookies_sessao, restaurar_cookies_sessao
    
    # No início do fluxo N8N
    restaurar_cookies_sessao(page, cdp_url)
    
    # Ao final ou periodicamente
    salvar_cookies_sessao(page, cdp_url)
"""

import json
import os
import logging
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

# Diretório de cache para cookies
COOKIES_DIR = os.path.join(os.path.expanduser("~"), ".cache", "timeline_clicker", "sessions")
COOKIES_FILE_TEMPLATE = os.path.join(COOKIES_DIR, "cookies_{url_hash}.json")
STORAGE_FILE_TEMPLATE = os.path.join(COOKIES_DIR, "storage_{url_hash}.json")
SESSION_STATE_TEMPLATE = os.path.join(COOKIES_DIR, "session_{url_hash}.json")


def _garantir_diretorio_cookies():
    """Cria diretório de armazenamento de cookies se não existir."""
    os.makedirs(COOKIES_DIR, exist_ok=True)
    logger.debug(f"✓ Diretório de cookies garantido: {COOKIES_DIR}")


def _calcular_hash_url(url: str) -> str:
    """Calcula hash da URL para identificar sessões diferentes."""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def _extrair_dominio(url: str) -> str:
    """Extrai domínio da URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "local"
    except Exception:
        return "local"


def salvar_cookies_sessao(page, url_pagina: str = None):
    """
    Salva cookies, storage local/session e estado de autenticação.
    
    Args:
        page: Página Playwright
        url_pagina: URL para identificar a sessão (default: page.url)
    
    Returns:
        dict com informações do salvamento
    """
    _garantir_diretorio_cookies()
    
    url = url_pagina or page.url
    url_hash = _calcular_hash_url(url)
    dominio = _extrair_dominio(url)
    
    try:
        # 1. Salva cookies
        cookies = page.context.cookies()
        cookies_file = COOKIES_FILE_TEMPLATE.format(url_hash=url_hash)
        
        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump({
                'url': url,
                'dominio': dominio,
                'timestamp': datetime.now().isoformat(),
                'cookies': cookies,
                'url_hash': url_hash
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ {len(cookies)} cookies salvos para {dominio} ({url_hash})")
        
        # 2. Salva localStorage e sessionStorage
        storage_data = page.evaluate(r"""
        () => {
            return {
                localStorage: JSON.stringify(localStorage),
                sessionStorage: JSON.stringify(sessionStorage)
            };
        }
        """)
        
        storage_file = STORAGE_FILE_TEMPLATE.format(url_hash=url_hash)
        with open(storage_file, 'w', encoding='utf-8') as f:
            json.dump({
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'localStorage': storage_data.get('localStorage', '{}'),
                'sessionStorage': storage_data.get('sessionStorage', '{}')
            }, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"✓ Storage local/session salvo para {url_hash}")
        
        # 3. Salva tokens de autenticação (se houver)
        auth_tokens = page.evaluate(r"""
        () => {
            return {
                localStorage_tokens: {
                    auth_token: localStorage.getItem('auth_token'),
                    refresh_token: localStorage.getItem('refresh_token'),
                    access_token: localStorage.getItem('access_token'),
                },
                sessionStorage_tokens: {
                    auth_token: sessionStorage.getItem('auth_token'),
                    bearer_token: sessionStorage.getItem('bearer_token'),
                },
                cookies_secure: document.cookie
            };
        }
        """)
        
        session_file = SESSION_STATE_TEMPLATE.format(url_hash=url_hash)
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump({
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'auth_tokens': auth_tokens
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ Estado de sessão salvo para {url_hash}")
        
        return {
            "status": "sucesso",
            "cookies_salvos": len(cookies),
            "arquivo_cookies": cookies_file,
            "arquivo_storage": storage_file,
            "arquivo_sessao": session_file,
            "url_hash": url_hash,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"Erro ao salvar cookies: {e}")
        return {
            "status": "erro",
            "mensagem": str(e),
            "url_hash": url_hash
        }


def restaurar_cookies_sessao(page, url_pagina: str = None):
    """
    Restaura cookies, storage local/session sem recarregar a página.
    
    Args:
        page: Página Playwright
        url_pagina: URL para identificar a sessão (default: page.url)
    
    Returns:
        dict com informações da restauração
    """
    _garantir_diretorio_cookies()
    
    url = url_pagina or page.url
    url_hash = _calcular_hash_url(url)
    dominio = _extrair_dominio(url)
    
    try:
        cookies_file = COOKIES_FILE_TEMPLATE.format(url_hash=url_hash)
        
        if not os.path.exists(cookies_file):
            logger.debug(f"Nenhum cookie salvo encontrado para {url_hash}")
            return {
                "status": "nenhum_cache",
                "mensagem": f"Nenhuma sessão anterior para {dominio}",
                "url_hash": url_hash
            }
        
        # 1. Restaura cookies
        with open(cookies_file, 'r', encoding='utf-8') as f:
            cookie_data = json.load(f)
        
        cookies = cookie_data.get('cookies', [])
        
        # Adiciona cookies ao contexto (não causa reload)
        for cookie in cookies:
            try:
                page.context.add_cookies([cookie])
            except Exception as e:
                logger.debug(f"Cookie não pôde ser restaurado: {cookie.get('name')} - {e}")
        
        logger.info(f"✓ {len(cookies)} cookies restaurados para {dominio}")
        
        # 2. Restaura localStorage e sessionStorage SEM RECARREGAR
        storage_file = STORAGE_FILE_TEMPLATE.format(url_hash=url_hash)
        if os.path.exists(storage_file):
            with open(storage_file, 'r', encoding='utf-8') as f:
                storage_data = json.load(f)
            
            local_storage = storage_data.get('localStorage', '{}')
            session_storage = storage_data.get('sessionStorage', '{}')
            
            # Injeta storage sem recarregar página
            page.evaluate(rf"""
            (data) => {{
                // Restaura localStorage
                try {{
                    const localData = JSON.parse(data.localStorage);
                    Object.keys(localData).forEach(key => {{
                        localStorage.setItem(key, localData[key]);
                    }});
                }} catch (e) {{
                    console.warn('Erro ao restaurar localStorage:', e);
                }}
                
                // Restaura sessionStorage
                try {{
                    const sessionData = JSON.parse(data.sessionStorage);
                    Object.keys(sessionData).forEach(key => {{
                        sessionStorage.setItem(key, sessionData[key]);
                    }});
                }} catch (e) {{
                    console.warn('Erro ao restaurar sessionStorage:', e);
                }}
                
                return true;
            }}
            """, {
                'localStorage': local_storage,
                'sessionStorage': session_storage
            })
            
            logger.debug(f"✓ Storage local/session restaurado para {url_hash}")
        
        # 3. Restaura tokens de autenticação
        session_file = SESSION_STATE_TEMPLATE.format(url_hash=url_hash)
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            auth_tokens = session_data.get('auth_tokens', {})
            
            # Restaura tokens em localStorage e sessionStorage
            page.evaluate(rf"""
            (tokens) => {{
                // Restaura tokens localStorage
                if (tokens.localStorage_tokens) {{
                    Object.entries(tokens.localStorage_tokens).forEach(([key, value]) => {{
                        if (value) localStorage.setItem(key, value);
                    }});
                }}
                
                // Restaura tokens sessionStorage
                if (tokens.sessionStorage_tokens) {{
                    Object.entries(tokens.sessionStorage_tokens).forEach(([key, value]) => {{
                        if (value) sessionStorage.setItem(key, value);
                    }});
                }}
                
                return true;
            }}
            """, {'localStorage_tokens': auth_tokens.get('localStorage_tokens', {}),
                  'sessionStorage_tokens': auth_tokens.get('sessionStorage_tokens', {})})
            
            logger.info(f"✓ Tokens de autenticação restaurados para {url_hash}")
        
        # 4. Verifica se sessão foi restaurada com sucesso
        verificacao = page.evaluate(r"""
        () => {
            return {
                tem_localStorage: Object.keys(localStorage).length > 0,
                tem_sessionStorage: Object.keys(sessionStorage).length > 0,
                tem_cookies: document.cookie.length > 0,
                titulo_pagina: document.title,
                url_atual: window.location.href
            };
        }
        """)
        
        logger.info(f"✓ Sessão restaurada com sucesso para {dominio}")
        logger.debug(f"  Verificação: {verificacao}")
        
        return {
            "status": "sucesso",
            "cookies_restaurados": len(cookies),
            "url_hash": url_hash,
            "verificacao": verificacao,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.exception(f"Erro ao restaurar cookies: {e}")
        return {
            "status": "erro",
            "mensagem": str(e),
            "url_hash": url_hash
        }


def limpar_sessoes_antigas(dias: int = 7):
    """
    Remove arquivos de sessão mais antigos que N dias.
    
    Args:
        dias: Número de dias (default: 7)
    
    Returns:
        dict com informações de limpeza
    """
    _garantir_diretorio_cookies()
    
    from datetime import timedelta
    agora = datetime.now()
    limite_tempo = agora - timedelta(days=dias)
    
    removidos = 0
    try:
        for arquivo in os.listdir(COOKIES_DIR):
            caminho = os.path.join(COOKIES_DIR, arquivo)
            if os.path.isfile(caminho):
                tempo_modificacao = datetime.fromtimestamp(os.path.getmtime(caminho))
                if tempo_modificacao < limite_tempo:
                    os.remove(caminho)
                    removidos += 1
                    logger.debug(f"Sessão antiga removida: {arquivo}")
        
        logger.info(f"✓ {removidos} sessões antigas removidas")
        return {
            "status": "sucesso",
            "sessoes_removidas": removidos,
            "dias_limite": dias
        }
    except Exception as e:
        logger.exception(f"Erro ao limpar sessões antigas: {e}")
        return {
            "status": "erro",
            "mensagem": str(e)
        }


def listar_sessoes_cached():
    """
    Lista todas as sessões em cache.
    
    Returns:
        list de dicts com informações das sessões
    """
    _garantir_diretorio_cookies()
    
    sessoes = []
    try:
        for arquivo in os.listdir(COOKIES_DIR):
            if arquivo.startswith('cookies_'):
                caminho = os.path.join(COOKIES_DIR, arquivo)
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        dados = json.load(f)
                    sessoes.append({
                        "arquivo": arquivo,
                        "url": dados.get('url'),
                        "dominio": dados.get('dominio'),
                        "timestamp": dados.get('timestamp'),
                        "cookies_count": len(dados.get('cookies', []))
                    })
                except Exception as e:
                    logger.debug(f"Erro ao ler sessão {arquivo}: {e}")
        
        return {
            "status": "sucesso",
            "total_sessoes": len(sessoes),
            "sessoes": sessoes
        }
    except Exception as e:
        logger.exception(f"Erro ao listar sessões: {e}")
        return {
            "status": "erro",
            "mensagem": str(e)
        }
