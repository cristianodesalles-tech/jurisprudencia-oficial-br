# Operação do acervo próprio

## Modos

- **Local:** SQLite, arquivos por SHA-256 e embedding determinístico. Usar para desenvolvimento, testes e pequenos acervos. Não chamar o embedding determinístico de busca semântica neural.
- **Produção:** PostgreSQL/pgvector, MinIO/S3, Redis/RQ, FastAPI e Sentence Transformers multilíngue.

## Comandos

```bash
python3 scripts/jurisprudencia_cli.py corpus-health
python3 scripts/jurisprudencia_cli.py search "tese" --state GO --branch civil
python3 scripts/jurisprudencia_cli.py ingest-url --metadata documento.json
python3 scripts/jurisprudencia_cli.py bulk-import --file lote.jsonl --source-id fonte --source-url https://dominio.jus.br/lote --court STJ
python3 scripts/jurisprudencia_cli.py review --document-id ID --checklist revisao.json
```

## Invariantes

1. Aceitar ingestão remota somente por HTTPS em domínio `.jus.br`, sem credenciais na URL e sem destino de rede privada.
2. Preservar conteúdo bruto imutável e SHA-256 antes de normalizar.
3. Deduplicar pelo conteúdo canônico, sem apagar versões anteriores silenciosamente.
4. Tratar lote/espelho como descoberta, salvo prova de que contém inteiro teor oficial apto a validação.
5. Não desativar TLS, não contornar CAPTCHA e não automatizar portal contra seus controles.
6. Exigir API key na API interna e não expor PostgreSQL, Redis ou MinIO publicamente.
7. Verificar a cadeia de auditoria e backups antes de promover versão.

## Falhas

Em erro transitório, repetir até o limite e abrir circuit breaker após falhas consecutivas. Em mudança de portal, resolver o novo endereço a partir do hub oficial e submeter alteração de configuração à revisão. Em `401`, `403`, `429` ou CAPTCHA, interromper; não criar bypass.
