# Evolução após a versão local 0.2

Já integrados: HTML e Selenium local, screenshot, metadados de cookies, rubrica explicável, progresso, interpretação Gemini opcional, histórico e PDF. A implementação não equivale a validação experimental de precisão.

1. **Validação para o TCC:** conjunto de páginas controladas e páginas autorizadas, referência humana, falsos positivos/negativos por critério, avaliação da IA, registro de modelo e repetibilidade. Comparar modos rápido/dinâmico sem inventar resultados.
2. **Consentimento:** sessões separadas antes/depois de aceitar/rejeitar, revogação, cookies/rastreadores conhecidos e teste de bloqueio, com critérios explícitos de aplicabilidade. Não classificar automaticamente um domínio desconhecido como rastreador.
3. **Cobertura:** shadow DOM/iframes, conteúdo carregado por interação, melhores regras para distinguir o corpo da política de outros textos e observação configurável com limites.
4. **Uso local:** exclusão/retensão configurável do histórico e capturas, comparação de análises, exportação estruturada e cancelamento pelo usuário. A chave UI hoje é volátil por decisão de segurança/usabilidade.
5. **IA:** teste real com chave do usuário, avaliação de aderência das citações ao tema, custo/latência, limites por conta e opção de provedor local. Nenhum modelo determina conformidade ou altera a nota sozinho.
6. **Isolamento:** contenção em sistema operacional/contêiner e controle de egress fora do navegador. Proxy e flags atuais não equivalem a contenção hermética.
7. **Hospedagem futura (fora do escopo local):** autenticação, isolamento de tarefas/usuários, armazenamento seguro, fila durável, limites de uso, WSGI/TLS e revisão antes de expor a aplicação.

O TCC deve distinguir funções implementadas, testes controlados, teste externo funcional e experimentos de precisão ainda não realizados.
