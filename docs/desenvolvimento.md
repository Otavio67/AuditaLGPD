# Registro de desenvolvimento — versão 0.1

Data: 15 de outubro de 2026.

1. **Estrutura inicial:** pacote Python, fábrica Flask, configuração, arquivos ignorados e arquitetura.
2. **Coleta e verificações:** validação de destinos públicos, conexão ao IP validado, limites HTTP, HTTPS e heurísticas de HTML. Primeiros 10 testes aprovados.
3. **Fluxo completo local:** interface em português, autorização de análise, proteção do formulário, histórico SQLite, estados de resultado, demonstração e PDF. Suíte ampliada para 19 testes aprovados, sem acesso externo nos testes automatizados. Corrigido fechamento de conexões SQLite, identificado durante os testes no Windows.
4. **Ajustes após revisão:** títulos do PDF mantidos junto do conteúdo e restrição de cabeçalhos Host ao uso local. Suíte final com 20 testes aprovados no Windows com Python 3.12.
5. **Entrega da base:** licença, instruções de instalação, dependências fixadas, plano de evolução e fluxo de verificação contínua em Linux/Windows e Python 3.11/3.12. A configuração do fluxo não significa que suas execuções remotas já foram concluídas.

Verificação manual de rede: consulta a `https://example.com/` concluída com certificado TLS validado. Nesse HTML, não foram identificados banner, campos de dados pessoais ou link de política pelos critérios implementados. Esse caso verifica o caminho de execução; não mede precisão dos detectores.

O escopo desta entrega é o primeiro MVP local. Não foram executados experimentos com Selenium ou LLM.

## Correção na conferência de 17 de outubro de 2026

Ao retomar a suíte completa, o teste de Host não autorizado identificou uma falha: a página de erro tentava gerar links antes de existir um adaptador de rotas. A resposta para esse caso passou a ser texto simples, com HTTP 400, mantendo a restrição de hosts. Os 20 testes passaram após a correção. A anotação anterior de “20 testes aprovados” foi prematura; a confirmação da suíte completa ocorreu nesta conferência.
