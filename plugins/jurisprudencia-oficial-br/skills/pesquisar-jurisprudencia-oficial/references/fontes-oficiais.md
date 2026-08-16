# Fontes oficiais e papéis

Atualizado em 16 de agosto de 2026. Revalidar URLs antes de uso.

| Fonte | Papel permitido | Observação |
|---|---|---|
| CNJ DataJud | descoberta e metadados processuais | Não prova jurisprudência nem inteiro teor. Usa endpoints por tribunal. |
| TJGO Pesquisa de Jurisprudência/PROJUDI | pesquisa e validação local | Consultar `https://projudi.tjgo.jus.br/ConsultaJurisprudencia`. |
| STJ SCON | pesquisa, espelho e acesso ao inteiro teor | Consultar `https://scon.stj.jus.br/SCON/`. |
| STJ Dados Abertos | descoberta estruturada e acervos | CKAN em `https://dadosabertos.web.stj.jus.br/api/3/action/`; confirmar no SCON/inteiro teor. |
| STF Jurisprudência | pesquisa, espelho, repercussão geral e inteiro teor | Consultar `https://jurisprudencia.stf.jus.br/pages/search`. |
| TRT18 Jurisprudência | pesquisa e validação regional | Partir de `https://www.trt18.jus.br/portal/jurisprudencia/` e usar os links oficiais Falcão/Jurisprudência–TRT. |
| TST Jurisprudência | pesquisa no inteiro teor e validação superior trabalhista | Consultar `https://jurisprudencia.tst.jus.br/`. |

## DataJud

Base: `https://api-publica.datajud.cnj.jus.br`. Exemplos: `/api_publica_tjgo/_search`, `/api_publica_trt18/_search`, `/api_publica_stj/_search`, `/api_publica_tst/_search`. Usar a documentação oficial vigente e credencial obtida legitimamente. Não embutir chaves no repositório.

## Classificação de fontes

- **Primária:** portal do tribunal, inteiro teor, diário oficial, repositório oficial de precedentes.
- **Estruturada oficial:** API/dados abertos do próprio órgão; confirmar escopo e atualização.
- **Secundária:** notícia institucional, informativo ou publicação de pesquisa; útil para descoberta e contexto.
- **Terceira:** agregador privado, blog, buscador geral; apenas pista.

Quando uma página oficial disser que um material não é repositório oficial, respeitar o aviso e revalidar cada julgado individualmente.
