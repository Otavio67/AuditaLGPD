# AuditaLGPD

Ferramenta acadêmica para diagnóstico técnico preliminar de elementos públicos de páginas web relacionados à privacidade. O resultado não certifica conformidade jurídica com a LGPD.

## Desenvolvimento por etapas

1. Estrutura Python e aplicação Flask.
2. Coleta HTTP limitada e verificações de HTML.
3. Histórico SQLite e fluxo da auditoria.
4. Interface em português e exportação PDF.
5. Testes, documentação e integração contínua.

Cada etapa será registrada em um commit próprio. A implementação começa com HTML recebido por HTTP; renderização de JavaScript com Selenium e análise com LLM ficam para incrementos posteriores e serão identificadas como não executadas enquanto não estiverem integradas.

## Executar localmente

Requer Python 3.11 ou superior.

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m flask --app auditalgpd run --host 127.0.0.1 --port 5000
```

O servidor de desenvolvimento é destinado ao uso local. Arquivos de banco de dados, segredos, relatórios e documentos acadêmicos pessoais ficam fora do Git.
