# Estratégia de busca e fallback

## Decomposição

Para cada tese, montar uma matriz com: questão, regra, exceção, fato-âncora, dispositivo, termos do tribunal, resultado favorável, resultado contrário e autoridade desejada.

## Escada de consultas

1. Expressão jurídica exata + fato-âncora.
2. Dispositivo legal + consequência jurídica.
3. Sinônimos e vocabulário do tribunal.
4. Classe/processo/órgão julgador.
5. Tema qualificado, súmula, IRDR, IAC, repetitivo ou repercussão geral.
6. Consulta ampla e filtragem manual do inteiro teor.
7. Busca pelo número em consulta processual, diário e repositório oficial.

Combinar datas de julgamento e publicação. Preferir recentes, mas preservar leading cases e precedentes vinculantes vigentes.

## Fallback regenerativo

Em erro transitório: repetir com backoff curto, registrar status HTTP e trocar `HEAD` por `GET` quando necessário. Em mudança de portal: começar pela página institucional de jurisprudência, localizar o novo destino e atualizar apenas a configuração. Em resultado vazio: remover filtros progressivamente, trocar a ordem dos termos e usar sinônimos. Em documento ilegível: tentar HTML oficial, PDF oficial alternativo, consulta processual e diário oficial.

Quando fetch, robots.txt ou renderização JavaScript impedirem a automação, usar o Chrome interativo no portal oficial: abrir a pesquisa, preencher os campos, executar, paginar, abrir o registro e baixar o inteiro teor. Registrar as consultas e URLs efetivamente usadas. Não substituir esse passo por agregador privado.

Antes de declarar resultado negativo em tribunal obrigatório, executar no mínimo: três consultas semanticamente distintas; uma consulta por dispositivo; uma por classe ou órgão; e a tentativa interativa no portal, quando disponível. A falta de fatos detalhados reduz aderência, mas não impede pesquisa temática geral.

Não contornar autenticação, CAPTCHA, rate limit ou controle de acesso. Não raspar agressivamente. Respeitar termos e robots; preferir exportação/API oficial.

## Busca adversarial

Executar consultas com: “distinção”, “distinguishing”, “superado”, “cancelado”, “modulação”, “afetação”, “suspensão”, “não se aplica”, “divergência”, “ressalva” e a formulação contrária da tese.

## Critério de parada

Registrar saturação quando novas consultas não acrescentarem autoridade ou fatos relevantes, a cobertura hierárquica estiver atendida e todos os candidatos úteis tiverem inteiro teor conferido. Se a cobertura mínima não for alcançada apó toda a escada, inclusive navegador, emitir relatório negativo detalhado; nunca preencher lacunas por memória nem pedir ao usuário um número de processo como condição para continuar uma busca temática.
