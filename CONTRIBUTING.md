# Contribuindo

Pull requests de fontes e conectores devem incluir: URL oficial, documentação de escopo, classificação (descoberta ou validação), tratamento de rate limit, teste sem credenciais e atualização da data do registro.

Não envie chaves, cookies, documentos sigilosos ou dados pessoais. Não adicione scraping que contorne CAPTCHA, autenticação ou termos de uso. Toda mudança na política anti-alucinação precisa preservar falha fechada.

Execute:

```bash
python3 -m unittest discover -s plugins/jurisprudencia-oficial-br/tests -v
python3 /caminho/para/skill-creator/scripts/quick_validate.py plugins/jurisprudencia-oficial-br/skills/pesquisar-jurisprudencia-oficial
python3 /caminho/para/plugin-creator/scripts/validate_plugin.py plugins/jurisprudencia-oficial-br
```
