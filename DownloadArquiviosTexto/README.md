# Download de Arquivos de Texto

Projeto para extração e consolidação de textos de elementos dentro de iframes em páginas web, salvando o conteúdo em arquivos `.txt`.

## Estrutura do Projeto

- **navegador.py**: Gerencia conexão com o navegador via CDP (Chrome DevTools Protocol)
- **extrator_texto.py**: Lógica para extração e consolidação de textos
- **orquestrador.py**: Orquestra o fluxo de extração
- **main.py**: Ponto de entrada da aplicação

## Uso

```bash
python3 /path/to/main.py <numero_processo> <id_documento> [seletor_div]
```

### Exemplos

#### Com seletor padrão (div)
```bash
python3 main.py "0802288-06.2026.8.18.0031" "100487677"
```

#### Com seletor customizado
```bash
python3 main.py "0802288-06.2026.8.18.0031" "100487677" "p"
```

## Parâmetros

- `numero_processo` (obrigatório): Número do processo, usado para criar a pasta de destino
- `id_documento` (obrigatório): ID do documento, usado como nome do arquivo gerado
- `seletor_div` (opcional): Seletor CSS para os elementos a extrair (padrão: "div")

## Variáveis de Ambiente

- `CDP_URL`: URL do Chrome DevTools Protocol (padrão: http://localhost:9222)

## Saída

A aplicação retorna um JSON com o seguinte formato:

```json
{
  "status": "sucesso",
  "caminho_arquivo": "/path/to/arquivo.txt",
  "nome_arquivo": "arquivo.txt",
  "quantidade_textos": 42,
  "tamanho_bytes": 5242,
  "numero_processo": "0802288-06.2026.8.18.0031",
  "id_documento": "100487677",
  "pasta_destino": "/path/to/pasta",
  "titulo_pagina": "Título da página",
  "url_pagina": "https://exemplo.com"
}
```

### Em caso de erro:

```json
{
  "status": "erro",
  "numero_processo": "0802288-06.2026.8.18.0031",
  "id_documento": "100487677",
  "mensagem": "Descrição do erro"
}
```

## Características

- ✅ Extração de textos de elementos dentro de iframes
- ✅ Consolidação inteligente com remoção de duplicatas
- ✅ Separação adequada entre textos
- ✅ Normalização de nomes de arquivo
- ✅ Prevenção de sobrescrita de arquivos
- ✅ Suporte a seletores CSS customizados
- ✅ Tratamento robusto de erros
- ✅ Compatibilidade com Chrome DevTools Protocol

## Dependências

- `playwright`: Para automação do navegador
- Python 3.7+

## Instalação

```bash
pip install playwright
python -m playwright install chromium
```