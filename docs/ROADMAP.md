# Plano de evolução

A versão 0.1 implementa um diagnóstico baseado em HTML estático, com histórico e PDF. As etapas abaixo ainda não foram executadas e dependem de implementação e validação próprias.

## 1. Melhorar a base de evidências

- Criar um conjunto de páginas controladas, com e sem banner, formulários e política, incluindo português e inglês.
- Comparar os resultados com revisão humana e registrar falsos positivos e falsos negativos.
- Distinguir visibilidade observada no navegador de indícios presentes apenas no HTML.
- Implementar remoção de auditorias e uma política de retenção local.

## 2. Renderização com Selenium

- Isolar o navegador coletor em processo/ambiente separado e restringir sua rede. A validação do HTTP atual não protege as requisições feitas por um navegador que executa JavaScript.
- Estabelecer limites de páginas, tempo, memória e tamanho de evidências.
- Capturar estados antes e depois de escolhas de consentimento em páginas autorizadas, sem enviar formulários com dados pessoais.
- Testar coleta e bloqueio de cookies/rastreadores com cenários reproduzíveis.

## 3. Análise assistida por IA

- Definir provedor/modelo e requisitos de custo, privacidade e retenção antes de qualquer integração.
- Separar instruções da aplicação de textos não confiáveis dos sites; não permitir que políticas ou páginas emitam comandos para o sistema.
- Solicitar observações estruturadas com trechos de evidência e possibilidade de abstenção.
- Avaliar as respostas com casos revisados por humanos. A IA não deve emitir certificação automática de conformidade.

## 4. Preparar eventual hospedagem

- Adicionar autenticação, autorização e isolamento de dados entre usuários.
- Adicionar filas, limites por usuário, controles de saída de rede, limites rígidos por tarefa e monitoramento.
- Revisar retenção, exclusão e tratamento de URLs e evidências.
- Usar servidor de produção, TLS e armazenamento protegido; executar revisão de segurança antes de exposição pública.

## Relação com o TCC

Registrar no artigo somente as funcionalidades implementadas e as validações efetivamente realizadas. Uma suíte de testes técnicos não demonstra, por si só, eficácia jurídica nem qualidade de um modelo de IA. Resultados experimentais de Selenium e LLM devem ser apresentados apenas depois dos experimentos.
