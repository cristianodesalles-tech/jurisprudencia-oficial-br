# Configuração para Cowork e agentes compatíveis

Use `AGENTS.md` como instrução persistente e registre o MCP com:

```json
{
  "mcpServers": {
    "jurisprudencia-oficial-br": {
      "command": "python3",
      "args": ["/caminho/absoluto/jurisprudencia-oficial-br/plugins/jurisprudencia-oficial-br/mcp/server.py"]
    }
  }
}
```

Substitua o caminho e mantenha o diretório do plugin como diretório de trabalho. Conceda rede somente para domínios oficiais necessários. Configure `DATAJUD_API_KEY` fora dos arquivos versionados.

O servidor oferece planejamento, validação, diagnóstico de fontes, consulta de metadados DataJud e descoberta no STJ Dados Abertos. A navegação nos portais continua necessária para ler o inteiro teor e avaliar aderência jurídica.
