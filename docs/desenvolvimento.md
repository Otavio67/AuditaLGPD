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

## Versão local 0.2 — 17 de outubro de 2026

- Publicados os commits existentes no repositório público Otavio67/AuditaLGPD após autenticação oficial pelo Git Credential Manager. Não foram publicados banco, perfis, chaves ou documentos pessoais.
- Adicionada rubrica acadêmica versionada com pesos, cobertura mínima e distinção entre ausência e falha. A nota não determina conformidade jurídica. Refinada a informação próxima aos formulários para não aprovar outros formulários por existir aviso em apenas um deles.
- Integrado Selenium 4.51.0 com Edge local 155.0.4283.45, processo separado, perfil temporário, proxy com destinos públicos/IP fixado, limite de execução e captura.
- A conferência real identificou tráfego de inicialização do Edge/MSN. O inventário foi corrigido para usar eventos dos frames/loaders da página atual; cookies de outros domínios não são atribuídos ao site analisado.
- Teste externo funcional em example.com: HTTP 200, captura e domínio example.com, sem cookies atribuídos. Fluxo completo executado também pelo formulário da interface, com progresso, gravação e abertura do relatório. Isso não é medição de precisão em um conjunto de sites.
- Teste controlado real `tools/smoke_browser.py`: banner inserido por JavaScript, detecção dos controles, cookie fictício, captura e exclusão de valores dos campos/cookies. Transporte de fixture injetado somente no teste.
- Integração Gemini por API REST, resposta estruturada e validação literal de citações. Testada com respostas simuladas, incluindo citação inventada, chave ausente, esquema inválido, remoção básica de identificadores e chave fora de arquivo/HTML. Nenhuma chamada real ao Gemini foi realizada sem chave do usuário.
- Painel com nota, indicadores, recomendações, estados com texto e cores, filtros, inventário e metodologia; conferido em desktop e viewport de 390 px, sem transbordamento horizontal do documento. Perfil pessoal do navegador não é usado pelo coletor.
- Exportação PDF conferida visualmente nas quatro páginas da demonstração, incluindo nota, pesos, revisão humana e limites. Título, estado e descrição das verificações permanecem juntos nas quebras de página.
- Suíte ampliada para 37 testes locais aprovados; `pip check` sem dependências quebradas. Testes GitHub Actions dos commits 33c3569 e 04ae152 concluídos com sucesso. O resultado remoto de cada commit deve ser consultado no Actions.

Permanecem pendentes: teste Gemini com chave real, experimentos de precisão, teste de escolhas/bloqueio/revogação de cookies, avaliação de processos internos LGPD e isolamento de sistema operacional. O TCC deve apresentar essas distinções.
