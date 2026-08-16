# Base de fontes oficiais pesquisada

Pesquisa atualizada em 16 de agosto de 2026.

- [CNJ — DataJud Wiki](https://datajud-wiki.cnj.jus.br/): define o DataJud como base nacional de metadados processuais. O plugin o limita a descoberta e cruzamento.
- [CNJ — tutorial da API Pública DataJud](https://www.cnj.jus.br/wp-content/uploads/2023/05/tutorial-api-publica-datajud-beta.pdf): documenta endpoints por tribunal, incluindo TJGO, TRT18, STJ e TST.
- [TJGO — Jurisprudência](https://www.tjgo.jus.br/index.php/processos/atos-judiciais-jurisprudencia): ponto institucional para o novo módulo PROJUDI.
- [TJGO — Consulta de Jurisprudência](https://projudi.tjgo.jus.br/ConsultaJurisprudencia): pesquisa oficial com termo, instância, área, órgão, magistrado, processo e datas.
- [STJ — Pesquisa SCON](https://scon.stj.jus.br/SCON/): pesquisa oficial e acesso aos registros jurisprudenciais.
- [STJ — Portal de Dados Abertos](https://dadosabertos.web.stj.jus.br/dataset/?groups=jurisprudencia): conjuntos em JSON/CSV/ZIP e API CKAN; cada julgado deve ser confirmado no SCON/inteiro teor.
- [STF — Dicas de pesquisa](https://portal.stf.jus.br/textos/verTexto.asp?pagina=Dicas_de_pesquisa&servico=jurisprudenciaPesquisaGeralNovoPortal): distingue espelho e inteiro teor, explica bases, filtros e alcance de texto integral.
- [TRT18 — hub de Jurisprudência](https://www.trt18.jus.br/portal/jurisprudencia/): reúne Falcão, jurisprudência regional, TST, precedentes e teses qualificadas.
- [TST — Pesquisa de Jurisprudência](https://jurisprudencia.tst.jus.br/): consulta oficial; a documentação do tribunal informa pesquisa no inteiro teor.

## Estratégia de fallback

API oficial documentada é preferida para escala; portal oficial é obrigatório para confirmação; diário/consulta processual oficial serve de fallback pelo número. Buscadores e bases privadas podem descobrir referências, mas nunca encerram a validação.

Não foram encontrados, na documentação pública consultada, contratos estáveis e universais de API de inteiro teor para todos esses tribunais. Por isso os conectores de portal são deliberadamente configuráveis, o monitor detecta mudanças, e o sistema falha fechado em vez de depender de scraping oculto e frágil.
