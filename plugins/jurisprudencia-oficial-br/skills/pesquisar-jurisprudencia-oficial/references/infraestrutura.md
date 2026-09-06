# Operação do acervo próprio

## Modos

- **Local:** SQLite, arquivos por SHA-256 e embedding determinístico. Usar para desenvolvimento, testes e pequenos acervos. Não chamar o embedding determinístico de busca semântica neural.
- **Produção:** PostgreSQL/pgvector, MinIO/S3, Redis/RQ, FastAPI e Sentence Transformers multilíngue.

## Onde mora o acervo

`~/.local/share/jurisprudencia-oficial-br`, ou o caminho de `STATE_DIR`. Fora do pacote de propósito: atualizar o plugin não pode apagar acervo nem curadoria. O registro de superação segue a mesma regra; o arquivo dentro de `config/` é semente vazia.

## Comandos

```bash
python3 scripts/jurisprudencia_cli.py corpus-health
python3 scripts/jurisprudencia_cli.py search "tese" --state GO --branch civil
python3 scripts/jurisprudencia_cli.py ingest-url --metadata documento.json
python3 scripts/jurisprudencia_cli.py bulk-import --file lote.jsonl --source-id fonte --source-url https://dominio.jus.br/lote --court STJ
python3 scripts/jurisprudencia_cli.py review --document-id ID --checklist revisao.json
python3 scripts/jurisprudencia_cli.py capture-assisted --metadata captura.json --file pagina.html --operator "Nome Completo" --oab "GO 00000"
python3 scripts/jurisprudencia_cli.py document --document-id ID
python3 scripts/jurisprudencia_cli.py chunk --document-id ID --ordinal 0
python3 scripts/jurisprudencia_cli.py overruling-add --entry superacao.json
python3 scripts/jurisprudencia_cli.py overruling-list
```

## Invariantes

1. Aceitar ingestão remota somente por HTTPS em domínio `.jus.br`, sem credenciais na URL e sem destino de rede privada.
2. Preservar conteúdo bruto imutável e SHA-256 antes de normalizar.
3. Deduplicar pelo conteúdo canônico, sem apagar versões anteriores silenciosamente.
4. Lote, espelho e exportação são sempre descoberta, sem exceção configurável. Inteiro teor só entra por busca individual na fonte oficial, com resposta HTTP 200 e hash conferido.
5. Não desativar TLS, não contornar CAPTCHA e não automatizar portal contra seus controles.
6. Exigir API key na API interna e não expor PostgreSQL, Redis ou MinIO publicamente.
7. Verificar a cadeia de auditoria e backups antes de promover versão.

## Falhas

Em erro transitório, repetir até o limite e abrir circuit breaker após falhas consecutivas. Em mudança de portal, resolver o novo endereço a partir do hub oficial e submeter alteração de configuração à revisão. Em `401`, `403`, `429` ou CAPTCHA, interromper; não criar bypass.
