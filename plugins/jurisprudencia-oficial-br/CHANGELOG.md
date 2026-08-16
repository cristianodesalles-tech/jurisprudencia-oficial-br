# Changelog

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
