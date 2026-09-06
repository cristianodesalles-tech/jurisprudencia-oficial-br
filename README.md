# Jurisprudência Oficial BR

Infraestrutura aberta e auditável para formar acervo próprio e pesquisar jurisprudência brasileira sem quota mensal de terceiros, com uma regra simples: **sem inteiro teor oficial, não há precedente validado**.

O projeto decompõe o caso em teses, planeja buscas na hierarquia adequada, consulta fontes oficiais, registra tentativas, valida metadados e integridade documental e produz uma matriz pronta para revisão humana. DataJud é usado somente para descoberta de metadados; o conteúdo jurídico deve ser confirmado no tribunal.

## O que está implementado

- Armazenamento imutável de documentos por SHA-256 em arquivos ou MinIO/S3.
- PostgreSQL 16 + pgvector em produção e SQLite para testes/operação local.
- Busca lexical e vetorial combinada por Reciprocal Rank Fusion.
- Reranking por força do precedente, vinculação, atualidade e tribunal local/superior.
- Importação JSON, JSONL, CSV e ZIP com proteção contra path traversal e zip bomb.
- API FastAPI autenticada, fila Redis/RQ, worker, métricas Prometheus e MCP.
- Circuit breaker, retentativas limitadas e registro versionado de fontes.
- Auditoria JSONL encadeada por hash, capaz de detectar adulteração.
- Revisão jurídica persistente antes da promoção a `VALIDADO`.
- Grau de evidência calculado pelo motor a partir de prova, nunca declarado por quem importa.
- Captura assistida para portais protegidos, com operador identificado e URL oficial preservada verbatim.
- Registro de superação em camada separada, alimentado só por curadoria com fonte oficial.
- Entrega de inteiro teor sem truncagem, com paginação por trecho.

## Cobertura

- Justiça estadual: TJ da unidade federativa + STJ + STF quando constitucional.
- Justiça do Trabalho: TRT competente + TST + STF quando constitucional.
- Roteamento de todos os TJs, TRTs e TRFs; pesquisa oficial automática no TRF1, DataJud e dados abertos do STJ.
- TJGO, STF e TRT18 operam em modo assistido enquanto seus portais não oferecerem um contrato público automatizável sem CAPTCHA/WAF.
- Precedentes qualificados/vinculantes antes de julgados meramente persuasivos.

## Garantias de segurança

- Estados explícitos: `PISTA`, `LOCALIZADO`, `CONFIRMADO`, `VALIDADO`, `REJEITADO`, `NÃO VALIDADO`.
- Quota mínima de dois julgados quando existentes, sem preencher lacunas com decisões inadequadas.
- Conferência de identidade, inteiro teor, ratio, aderência fática, vigência e entendimento contrário.
- Hash SHA-256 do documento e auditoria JSONL.
- Falha fechada: erro de rede, documento ausente ou domínio não oficial impede validação.
- Autoajuste restrito à estratégia de busca e recuperação; nunca altera evidência ou inventa campos.
- Isolamento de JurisRatio e de outros provedores privados com cota: o fluxo padrão usa somente acervo próprio, MCP, navegador e fontes oficiais.
- Erro de cota de ferramenta externa é tratado como falha de roteamento e não interrompe a pesquisa oficial.
- A skill instrui o agente a isolar provedores privados durante a pesquisa oficial e registra seleção indevida como erro de roteamento.
- Portais oficiais dinâmicos exigem fallback pelo Chrome; robots.txt ou JavaScript não encerram a busca enquanto a interface oficial estiver acessível.
- O backend do TST jamais é usado para rotular recursos do TST como se fossem acórdãos do TRT18.
- O selo `VALIDADO` exige arquivo oficial preservado e SHA-256; sem isso, o resultado permanece no máximo `CONFIRMADO`.

## Instalação no Codex

Instale primeiro o [Codex CLI](https://learn.chatgpt.com/docs/codex/cli):

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
exec zsh -l
```

Depois, clone o repositório público e instale o plugin pelo marketplace incluído:

```bash
git clone https://github.com/cristianodesalles-tech/jurisprudencia-oficial-br.git
cd jurisprudencia-oficial-br
codex plugin marketplace add "$PWD"
codex plugin add jurisprudencia-oficial-br@jurisprudencia-oficial-br
```

Reinicie o Codex ou abra uma nova tarefa e peça: “pesquise jurisprudência oficial aplicável a este caso”.

Código-fonte, atualizações e contribuições: [github.com/cristianodesalles-tech/jurisprudencia-oficial-br](https://github.com/cristianodesalles-tech/jurisprudencia-oficial-br).

## Instalação no Claude Code

O repositório também é um marketplace nativo do Claude Code. Não é necessário clonar para instalar:

```bash
claude plugin marketplace add cristianodesalles-tech/jurisprudencia-oficial-br
claude plugin install jurisprudencia-oficial-br@jurisprudencia-oficial-br --scope user
```

Abra uma nova sessão ou execute `/reload-plugins`. A skill fica disponível como
`/jurisprudencia-oficial-br:pesquisar-jurisprudencia-oficial` e o atalho como
`/jurisprudencia-oficial-br:pesquisar-jurisprudencia`. O servidor MCP solicita aprovação no primeiro uso.

Para atualizar uma instalação existente:

```bash
claude plugin marketplace update jurisprudencia-oficial-br
claude plugin update jurisprudencia-oficial-br@jurisprudencia-oficial-br
```

A estrutura segue a documentação oficial de [marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) e [plugins](https://code.claude.com/docs/en/plugins).

## Núcleo local

O núcleo requer Python 3.11+ e usa SQLite com índice FTS5, armazenamento em arquivos e embedding determinístico de contingência. Para busca semântica de verdade, defina `EMBEDDING_PROVIDER=sentence-transformers`, que usa modelo local e gratuito de 768 dimensões, já compatível com o esquema.

O acervo é gravado em `~/.local/share/jurisprudencia-oficial-br`, ou no caminho indicado por `STATE_DIR`. Fica fora do pacote de propósito: atualizar o plugin não pode apagar o acervo nem a curadoria de superação.

```bash
CLI=plugins/jurisprudencia-oficial-br/scripts/jurisprudencia_cli.py

python3 $CLI plan --case plugins/jurisprudencia-oficial-br/examples/caso.json
python3 $CLI corpus-health
python3 $CLI search "mero inadimplemento dano moral" --state GO

# portal protegido: conferência humana com prova do que foi lido
python3 $CLI capture-assisted --metadata captura.json --file pagina.html \
  --operator "Nome Completo" --oab "GO 00000"

# leitura longa sem truncagem
python3 $CLI document --document-id ID
python3 $CLI chunk --document-id ID --ordinal 0

# curadoria de superação
python3 $CLI overruling-add --entry superacao.json
python3 $CLI overruling-list

python3 -m unittest discover -s plugins/jurisprudencia-oficial-br/tests -v
```

### Como um julgado chega ao selo

`PISTA` e `LOCALIZADO` valem para lote, espelho e dados abertos, que entram sempre como descoberta. `CONFIRMADO` exige três provas juntas: fonte registrada que valida, resposta oficial com hash conferido e inteiro teor de verdade, ou então captura assistida com operador identificado. `VALIDADO` exige revisor humano com nome completo e OAB mais o SHA-256 do documento lido. Nenhum parâmetro promove documento, e o agente não assina a própria revisão.

## Infraestrutura de produção

Requer Docker com Compose:

```bash
python3 scripts/bootstrap.py
docker compose config
docker compose up -d --build
```

A API fica vinculada a `127.0.0.1:8080`; PostgreSQL, Redis e MinIO não publicam portas. Coloque um proxy TLS autenticado à frente da API somente quando acesso remoto for necessário.

```bash
docker compose ps
curl http://127.0.0.1:8080/health/live
```

Leia [implantação](docs/deployment.md), [pipeline de dados](docs/data-pipeline.md), [arquitetura](docs/architecture.md) e [modelo de ameaças](docs/threat-model.md).

Para DataJud, defina `DATAJUD_API_KEY` no ambiente. A chave nunca deve entrar no repositório.

## Clientes

- Codex: manifesto em `.codex-plugin/` e marketplace na raiz.
- Claude Code: marketplace GitHub em `.claude-plugin/marketplace.json`, manifesto próprio, skill, comando e servidor MCP isolado.
- Cowork/agentes: instruções em `AGENTS.md` e `clients/cowork.md`.
- Custom GPT: instruções e Action OpenAPI em `clients/`; o GPT precisa de navegação para validar o inteiro teor.

Consulte também a [política de validação](docs/validation-policy.md), as [fontes pesquisadas](docs/official-sources.md), o [protocolo clean-room](docs/clean-room.md) e o [guia de contribuição](CONTRIBUTING.md).

## Limites

O software auxilia pesquisa e auditoria; não substitui revisão jurídica profissional. A cobertura depende dos lotes e conectores efetivamente executados. Portais podem mudar, impor CAPTCHA ou indisponibilidade. O projeto não contorna controles de acesso nem trata resultados de modelos de linguagem como fonte.

Licença MIT.
