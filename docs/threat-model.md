# Modelo de ameaças

| Ameaça | Controle |
|---|---|
| Precedente inventado | Somente documentos persistidos; proveniência e hash obrigatórios |
| SSRF | HTTPS `.jus.br`, DNS público e validação após redirect |
| ZIP malicioso | Bloqueio de traversal, limite de arquivos/tamanho/razão |
| Alteração de evidência | Armazenamento por conteúdo e auditoria encadeada |
| Vazamento de serviços | Somente API em loopback; banco, Redis e MinIO internos |
| Credencial no repositório | `.env` ignorado, bootstrap aleatório e varredura em CI |
| Abuso de portal | limite de tamanho, user agent, circuit breaker e parada em controles |
| Promoção automática indevida | teto automático `CONFIRMADO`; checklist humano persistido |
| Envenenamento do ranking | fonte/role explícitos, deduplicação e sinais de autoridade explicáveis |
| Sequestro de dependência | versões/restrições, CI e recomendação de digest Docker em produção |

Riscos residuais: erro de extração PDF/OCR, metadados incorretos na origem, mudança legislativa ainda não indexada, decisão reformada e falha humana na revisão. A resposta deve sempre expor proveniência e limitações.
