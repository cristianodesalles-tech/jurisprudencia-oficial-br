# Changelog

## 0.5.0

- Captura assistida: TJGO, TRT18 e STF passam a poder chegar a `CONFIRMADO` por conferência humana identificada, com URL oficial verbatim e hash do que foi lido, sem contornar CAPTCHA ou WAF.
- Autoridade A a E derivada de tribunal, tipo documental e órgão julgador; alegação de precedente qualificado só levanta o nível depois do documento conferido na fonte.
- Súmulas, temas, OJ e enunciados passam a ocupar faixa própria e param de disputar o topo com acórdãos longos.
- Fixação exata quando o número do processo aparece literal na consulta.
- Recência com teto e portão de aderência, para que julgado novo não atropele precedente vinculante; penalidade para acórdão que discute processo e não a tese.
- Fim da truncagem silenciosa: `get_document` entrega o inteiro teor e `get_document_chunk` pagina repetindo os metadados.
- Registro de superação separado do índice, vazio por padrão, com curador identificado e fonte oficial obrigatórios; precedente superado sai do resultado salvo pedido expresso.
- Estado do acervo passa a morar em diretório estável do usuário, e não em variável inexistente nem dentro do pacote sincronizado.
- Índice FTS5 no SQLite no lugar da varredura em memória; trilha de auditoria deixa de reler o arquivo inteiro a cada gravação.
- Servidor MCP trata `ping`, `resources/list`, `prompts/list` e notificações, devolve código de erro correto e limita o tamanho da resposta.
- `pypdf` vira dependência base, já que ler inteiro teor em PDF é função central do plugin.

## 0.4.0

- O grau de evidência passa a ser calculado pelo motor (`engine/evidence.py`), não declarado por quem chama.
- `CONFIRMADO` exige as três provas juntas: fonte registrada que valida, resposta HTTP 200 oficial com hash conferido e inteiro teor real.
- Lote, espelho e exportação entram sempre como descoberta; o parâmetro que permitia forçar validação foi removido.
- Ementa deixa de ocupar o campo de inteiro teor e passa a ter coluna própria.
- `VALIDADO` exige revisor humano com nome completo e OAB, mais o SHA-256 do documento conferido; o agente não assina a própria revisão.
- Documento em `LOCALIZADO` ou `NÃO VALIDADO` deixa de ser promovível sem nova conferência estrutural.
- Filtro por UF deixa de eliminar STF, STJ, TST, TSE e STM, o que tornava a cobertura mínima local mais superior impossível.
- Acrescenta `tests/test_evidence_locks.py` travando cada um desses caminhos em regressão.

## 0.3.0

- Adiciona pesquisa oficial de baixa frequência no formulário CJF/TRF1, com sessão JSF e `ViewState`.
- Mantém todo resultado TRF1 como `NÃO VALIDADO` até a conferência do inteiro teor.
- Classifica TJGO, STF e TRT18 como fontes assistidas e registra suas proteções observadas.
- Impede a confusão entre recursos julgados no TST e acórdãos regionais do TRT18.
- Adiciona ferramentas MCP para TRF1, status das fontes e preparação de pesquisa assistida.

## 0.2.4

- Torna obrigatório o fallback pelo Chrome em portais oficiais dinâmicos ou bloqueados para fetch.
- Proíbe agregadores privados como descoberta automática.
- Exige arquivo oficial e SHA-256 para classificar qualquer precedente como `VALIDADO`.
- Impede que falta de número de processo fornecido pelo usuário encerre pesquisa temática.

## 0.2.3

- Adiciona bloqueio técnico `PreToolUse` para impedir chamadas ao conector global JusRatio enquanto a skill oficial estiver ativa.
- Mantém a JusRatio independente e utilizável fora do fluxo da Jurisprudência Oficial BR.

## 0.2.2

- Isola o fluxo de pesquisa de JurisRatio e outros provedores privados com cota.
- Trata respostas de limite externo como erro de roteamento e continua pelos fallbacks oficiais.
- Adiciona teste de contrato para impedir fontes privadas na configuração do plugin.

## 0.2.1

- Adiciona marketplace e manifesto nativos para Claude Code.
- Isola o estado persistente do MCP em `${CLAUDE_PLUGIN_DATA}`.
- Separa as configurações MCP de Claude e Codex.
- Documenta instalação direta pelo GitHub para Claude Code.

## 0.2.0

- Implementa corpus próprio, busca híbrida, validação jurídica e auditoria encadeada.
- Adiciona API, filas, armazenamento, observabilidade e infraestrutura Docker.
