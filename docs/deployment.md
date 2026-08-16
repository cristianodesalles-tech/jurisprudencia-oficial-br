# Implantação

## Desenvolvimento local

```bash
python3 scripts/doctor.py
python3 -m unittest discover -s plugins/jurisprudencia-oficial-br/tests -v
STATE_DIR=.state python3 plugins/jurisprudencia-oficial-br/scripts/jurisprudencia_cli.py corpus-health
```

## Produção com Docker Compose

1. Gerar segredos locais com `python3 scripts/bootstrap.py`.
2. Conferir `.env` e preencher `DATAJUD_API_KEY` somente se necessário.
3. Executar `docker compose config`.
4. Subir com `docker compose up -d --build`.
5. Confirmar `docker compose ps` e `/health/live`.
6. Consultar `/health/ready` com o cabeçalho `X-API-Key`.

O primeiro início com Sentence Transformers baixa o modelo multilíngue e pode consumir vários gigabytes. O fallback `hashing` é adequado para testes, não equivale a um modelo semântico neural.

## Segurança

- Manter `.env` com modo `0600` e fora do Git.
- Não publicar as portas de PostgreSQL, Redis ou MinIO.
- Manter a API em loopback ou rede privada; para acesso remoto, usar proxy TLS, autenticação e allowlist.
- Rotacionar `API_KEYS` e segredos dos serviços.
- Não armazenar cookies, tokens ou conteúdo de segredo de justiça na auditoria.
- Fixar digests das imagens Docker antes de produção regulada.

## Escala

Começar com um worker e busca exata/HNSW. Medir recall contra busca vetorial exata antes de ajustar índices. Adicionar workers horizontalmente para ingestão; manter migrações e atualização de modelo como mudanças versionadas.

## Backup

Executar backups consistentes do PostgreSQL e versionamento/replicação do bucket `jurisprudencia-raw`. Testar restauração periodicamente. O hash no banco deve coincidir com o metadado e o conteúdo restaurado do objeto.
