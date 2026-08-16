---
name: pesquisar-jurisprudencia-oficial
description: Pesquisar, indexar, validar, comparar e citar jurisprudência brasileira aplicável a caso concreto, com inteiro teor e fontes oficiais, sem depender de JurisRatio ou de provedores com cota. Usar sempre que o usuário pedir precedentes, julgados, acórdãos, súmulas, temas repetitivos, repercussão geral, pesquisa jurisprudencial para peça, validação de citação, atualização jurisprudencial ou manutenção do acervo próprio; priorizar tribunal local e superior competente, inclusive TJGO/STJ/STF e TRT18/TST/STF. Também usar para auditar existência, pertinência e integridade. Nunca inventar dados.
hooks:
  PreToolUse:
    - matcher: "mcp__claude_ai_jusratio__.*"
      hooks:
        - type: command
          command: "echo 'ERRO_DE_ROTEAMENTO_EXTERNO: JusRatio bloqueada durante a execução da Jurisprudência Oficial BR. Continue com mcp__jurisprudencia-oficial-br__, navegador e fontes oficiais.' >&2; exit 2"
---

# Pesquisar jurisprudência oficial

Aplicar o protocolo abaixo. Tratar toda referência ainda não confirmada como pista, nunca como precedente.

## Isolamento obrigatório de provedores

- Usar somente as ferramentas do MCP `jurisprudencia-oficial-br`, o acervo próprio, o navegador e domínios oficiais previstos em `fontes-oficiais.md`.
- Nunca chamar JurisRatio, Jusbrasil ou outro plugin, conector ou API privada de jurisprudência por seleção automática, mesmo que estejam instalados no ambiente.
- Não solicitar upgrade, assinatura, compra de créditos ou espera por renovação de cota para concluir a pesquisa.
- Se uma ferramenta externa devolver limite de cota, descartar sua resposta, registrar `ERRO_DE_ROTEAMENTO_EXTERNO` e prosseguir com fontes oficiais e fallbacks próprios.
- Não usar provedor privado nem mesmo como descoberta por iniciativa própria. Utilizá-lo somente quando o usuário o pedir expressamente e jamais como validação final.
- O hook `PreToolUse` desta skill deve bloquear tecnicamente todas as ferramentas `mcp__claude_ai_jusratio__.*` antes da chamada, sem interferir no uso da JusRatio fora desta skill.

## Carregar referências obrigatórias

1. Ler [politica-validacao.md](references/politica-validacao.md) integralmente antes de pesquisar.
2. Ler [fontes-oficiais.md](references/fontes-oficiais.md) para selecionar os portais e APIs.
3. Ler [estrategia-busca.md](references/estrategia-busca.md) ao decompor teses e executar fallbacks.
4. Ler [formato-entrega.md](references/formato-entrega.md) antes de redigir a resposta.
5. Ler [infraestrutura.md](references/infraestrutura.md) ao indexar, diagnosticar ou operar o acervo próprio.

## Executar o fluxo

1. Extrair fatos juridicamente relevantes, polo defendido, ramo, fase, tribunal/UF, datas críticas, pedidos, controvérsias, dispositivos e resultado pretendido.
2. Separar fato afirmado de inferência. Declarar lacunas que alterem competência, recorte temporal ou aderência.
3. Decompor o problema em teses atômicas e contrateses. Para cada tese, criar consultas por linguagem natural, termos técnicos, dispositivo, classe, tema e sinônimos.
4. Definir a hierarquia mínima:
   - justiça estadual: TJ da UF da parte defendida + STJ; adicionar STF apenas para questão constitucional real;
   - trabalho: TRT competente + TST; adicionar STF apenas para questão constitucional real;
   - federal: TRF competente + STJ; adicionar STF quando constitucional;
   - respeitar precedentes qualificados e vinculantes antes de julgados persuasivos.
5. Pesquisar fontes oficiais. Usar DataJud apenas para metadados/descoberta, nunca como prova do conteúdo do julgado.
   - Consultar primeiro o acervo próprio com `search_local_corpus`.
   - Ampliar nas fontes oficiais quando a cobertura estiver incompleta ou desatualizada.
   - Se fetch automatizado, robots.txt ou JavaScript impedirem a leitura, abrir o portal no Chrome e operar a interface oficial interativamente. Portal dinâmico não autoriza encerrar a pesquisa.
   - Antes de declarar fonte bloqueada, registrar ao menos três variações de consulta, tentativa por número/classe/dispositivo e tentativa no navegador oficial, salvo CAPTCHA ou controle de acesso objetivo.
6. Buscar ao menos dois precedentes materialmente aderentes quando existirem: um local/regional e um superior. Não completar quota com julgado inadequado.
7. Abrir e baixar o inteiro teor oficial de cada candidato. Conferir identidade, tese, fatos determinantes, resultado, vigência, superação e trechos citáveis no contexto. Calcular SHA-256 do arquivo e executar `validate_candidate`; sem arquivo e hash, o estado máximo é `CONFIRMADO`, nunca `VALIDADO`.
8. Fazer busca adversarial: procurar distinção, entendimento contrário, afetação, suspensão, modulação, cancelamento, superação e legislação posterior.
9. Revalidar cada metadado no portal oficial. Registrar URL, data/hora, método, hash do arquivo quando baixado e status de validação.
10. Somente então redigir a aplicação ao caso. Distinguir citação literal curta de paráfrase e indicar página/parágrafo quando disponível.

## Aplicar autoajuste limitado

Quando uma estratégia falhar, variar sinônimos, operadores, dispositivo, classe, intervalo de datas, órgão julgador e portal oficial. Em seguida, tentar fonte oficial equivalente e consulta pelo número do processo. Registrar cada tentativa e o motivo da mudança.

Nunca transformar erro de rede, ausência de resultado ou ambiguidade em confirmação. Se o inteiro teor permanecer inacessível, rotular `NÃO VALIDADO` e excluir o precedente do texto proposto para a peça.

Encerrar somente quando: (a) a matriz mínima validada estiver completa; (b) buscas razoáveis e diversificadas, inclusive pelo Chrome interativo, indicarem inexistência/indisponibilidade; ou (c) houver bloqueio externo objetivo, como CAPTCHA ou controle de acesso que não possa ser legitimamente superado. Robots.txt de fetch ou interface JavaScript, isoladamente, não são bloqueio objetivo quando o navegador está disponível. “Não encontrei ainda” exige ampliar a busca; “não existe” exige relatório negativo de consultas.

## Usar o mecanismo determinístico

Quando estiver disponível, executar `python3 scripts/jurisprudencia_cli.py plan --case caso.json` para gerar o plano e `python3 scripts/jurisprudencia_cli.py validate --candidate candidato.json --document acordao.pdf --audit auditoria.jsonl` para validar evidência. O servidor MCP expõe as mesmas operações.

Para o acervo próprio, usar `search`, `bulk-import`, `ingest-url`, `review` e `corpus-health`. Importações de espelhos e metadados permanecem `LOCALIZADO`; documento obtido de fonte oficial de validação pode chegar apenas a `CONFIRMADO`. Promover a `VALIDADO` exclusivamente com checklist jurídico completo e revisor identificado.

Não inserir credenciais, dados de segredo de justiça ou dados pessoais desnecessários nos artefatos de auditoria.
