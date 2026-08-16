# Política de validação

## Regra de ouro

Um resultado só recebe o selo `VALIDADO` se sua existência, identidade, conteúdo e pertinência forem conferidos em fonte oficial e no inteiro teor. Agregadores, notícias, informativos e modelos de linguagem servem para descoberta, nunca para validação final.

## Estados

- `PISTA`: menção ainda não confirmada.
- `LOCALIZADO`: registro encontrado em domínio oficial, sem inteiro teor conferido.
- `CONFIRMADO`: metadados essenciais coincidem com o documento oficial.
- `VALIDADO`: inteiro teor lido, ratio identificada, aderência e atualidade examinadas.
- `REJEITADO`: identidade, conteúdo, vigência ou aderência falhou.
- `NÃO VALIDADO`: verificação impedida; não citar na peça.

## Campos obrigatórios

Tribunal, classe e número, órgão julgador, relator, data de julgamento, data de publicação quando disponível, resultado, ementa, URL oficial do registro, URL/arquivo do inteiro teor, trecho aplicável, localização do trecho, tese sustentada, fatos determinantes, distinções, status e data/hora da verificação.

## Testes de validade

1. **Existência:** o processo/documento abre em domínio oficial.
2. **Identidade:** número, tribunal e órgão coincidem entre registro e documento.
3. **Integridade:** documento completo e legível; guardar SHA-256 quando baixado.
4. **Semântica:** o trecho existe literalmente ou está marcado como paráfrase fiel.
5. **Aderência:** fatos determinantes e questão jurídica são comparados ao caso.
6. **Autoridade:** competência, órgão, colegialidade e força do precedente são informadas.
7. **Atualidade:** verificar legislação posterior, reforma, afetação, cancelamento, superação e modulação.
8. **Adversarial:** procurar julgados contrários e distinguishing.

Falha em qualquer teste impede `VALIDADO`. Metadado ausente não deve ser inferido.

## Precedentes mínimos

Buscar no mínimo um precedente local/regional e um superior por tese central, totalizando ao menos dois quando existentes. Quantidade nunca substitui aderência. Se não houver dois precedentes válidos, entregar os encontrados e um relatório negativo contendo consultas, filtros, fontes, datas e limitações.

## Redação segura

Não usar “o tribunal decidiu” com base em snippet. Não atribuir tese ao voto vencido. Não ocultar resultado desfavorável ou distinção material. Não citar ementa como se fosse fundamento integral. Não declarar vinculante o que é apenas persuasivo.
