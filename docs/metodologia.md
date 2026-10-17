# Indicadores de privacidade — observaveis-1.0

Esta é uma rubrica acadêmica do AuditaLGPD, não uma escala oficial da ANPD nem uma certificação. A letra A–E significa somente proporção ponderada de sinais identificados nos critérios avaliados. Não autoriza afirmar que um site está juridicamente conforme.

## Cálculo reproduzível

Os pesos somam 100: HTTPS 10; link de política 10; acesso ao texto 5; finalidades 10; categorias de dados 5; compartilhamento 10; retenção 5; direitos 10; responsável e contato 10; explicação das bases legais 5; escolhas no aviso de cookies 10; informação junto ao formulário 10.

Nota = 100 × pontos identificados / pesos efetivamente avaliados, arredondada ao inteiro mais próximo. Erros, itens não executados e aplicabilidade indeterminada não entram no denominador. A cobertura mostra quantos dos 100 pontos puderam ser avaliados. Cobertura abaixo de 60% não produz nota ou letra. A: 90–100; B: 75–89; C: 60–74; D: 40–59; E: 0–39. Esses limiares são uma decisão de projeto, ainda sem validação empírica.

Os temas da política são identificados por vocabulário explícito e acompanhados de trecho literal. Termos isolados podem produzir falsos positivos. Redação diferente pode produzir falsos negativos. O item de responsável exige vocabulário de controlador e de canal de contato, mas não comprova que o atendimento funciona. O canal do controlador não equivale à obrigatoriedade universal de nomear encarregado.

O aviso de cookies só participa da nota quando é observado no navegador. Ausência de aviso não permite decidir sua obrigatoriedade. Aceitar, rejeitar e configurar são procurados como controles textuais; seu comportamento não é testado. Não ter formulários de dados pessoais deixa a aplicabilidade do critério em aberto.

Verde significa identificado; vermelho, não identificado pelos critérios; cinza, não verificado; laranja, erro/atenção. Essas cores descrevem detecção, inclusive para formulários e cookies, cuja presença não é aprovação legal.

A interpretação opcional do Gemini não altera a nota. A rubrica e a versão ficam registradas com a auditoria. Resultados históricos anteriores à introdução da rubrica são apresentados com indicação de cálculo atual, sem alterar os registros originais.

## Referências e limites

- [LGPD — texto oficial](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm): princípios, transparência, direitos, agentes e segurança. A avaliação interna precisa considerar o contexto do tratamento e as normas complementares aplicáveis.
- [ANPD — guia de cookies](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia_orientativo_cookies_e_protecao_de_dados_pessoais): orientação para transparência e escolhas sobre cookies.

É necessária avaliação humana da base legal, necessidade, dados sensíveis/infantis, contratos, transferências, atendimento de direitos, segurança interna e incidentes. A ferramenta não testa esses processos por consultar uma página pública.

## Pesquisa de interfaces e ferramentas — 17/10/2026

- [GTmetrix](https://gtmetrix.com/): referência de hierarquia visual — resumo, nota, métricas e detalhamento. Não é fonte de critérios de LGPD. Marca, conteúdo e ativos não foram copiados.
- [Cookiebot](https://www.cookiebot.com/en/cookie-checker/): inventário de cookies/rastreadores e relatório de risco; inspirou a separação entre evidências e interpretação.
- [CookieYes](https://www.cookieyes.com/cookie-scanner/): lista de cookies, categorias, páginas e histórico; inspirou o inventário local e a navegação por assuntos. Não se presume equivalência funcional com serviços comerciais ou aplicação automática de regras europeias à LGPD.
- [Gemini — API generateContent](https://ai.google.dev/api/generate-content) e [modelos](https://ai.google.dev/gemini-api/docs/models): integração opcional externa, com modelo configurável e validação local da resposta.

As funcionalidades declaradas pelos fornecedores foram consultadas em suas páginas oficiais. Não houve teste comparativo de precisão dessas plataformas.
