# Pipeline de dados

1. Descobrir fontes e lotes oficiais sem copiar bases privadas.
2. Classificar a fonte como `discovery` ou `validation`.
3. Baixar por HTTPS, validar domínio, DNS público, redirects, tamanho e tipo.
4. Guardar os bytes brutos em endereço derivado do SHA-256.
5. Extrair texto, normalizar Unicode e preservar metadados originais.
6. Deduplicar pelo conteúdo canônico; não sobrescrever versões silenciosamente.
7. Dividir em chunks com sobreposição limitada.
8. Produzir embeddings e indexar texto integral.
9. Registrar ingestão na cadeia de auditoria.
10. Manter como `LOCALIZADO` ou `CONFIRMADO` até revisão jurídica.

Lotes ZIP têm limites de quantidade, tamanho descompactado e razão de compressão; caminhos absolutos ou contendo `..` são rejeitados. Espelhos do STJ e metadados do DataJud são descoberta, mesmo quando oficiais.

## Busca

A consulta executa busca lexical e vetorial em paralelo, combina posições com RRF e aplica sinal jurídico separado. O sinal jurídico nunca cria documento nem substitui aderência: apenas ordena candidatos existentes.

## Atualização

Cada fonte deve manter cursor próprio, data de verificação e última execução. Nova versão do mesmo processo é preservada por hash. Remoção na origem não apaga automaticamente o objeto; exige política de retenção e análise de LGPD/publicidade processual.
