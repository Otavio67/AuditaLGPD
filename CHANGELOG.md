# Alterações

## Dependências — 20/11/2026

- reportlab 5.1.0, pillow 13.0.0, soupsieve 4.1.3, selenium 4.53.0 e atualizações menores (trio, certifi, click, pycparser); limite do reportlab ampliado para `<6`.
- Validação com 40 testes, smoke do navegador real, comparação visual do PDF e prints em `docs/validacao/2026-11-20-dependencias/`.

## Validação com sites reais — 20/11/2026

- Script `tools/validar_sites_reais.py`: executa a aplicação pelo formulário em sites reais e salva prints, PDFs, capturas e resumo JSON.
- Correção: a validação TLS da análise simples passou a usar as raízes do `certifi`; no Windows, certificados válidos eram recusados.
- Correção: um bloqueio HTTP 401/403/429 na análise avançada agora informa o código e sugere a análise simples.
- Correção: capturas acima de 1 MB são reduzidas em vez de descartadas.
- `certifi` e `pillow` declarados como dependências diretas. A suíte passou a ter 43 testes.

## Pacote portátil — 17/10/2026

- Distribuição Windows x64 com Python, dependências e navegador/driver incluídos.
- Launcher com abertura automática, porta livre, dados na própria pasta e prevenção de instâncias duplicadas.
- Preferência automática pelo navegador incluído, sem download de driver na primeira coleta.
- Gerador com fontes permitidas, hashes e licenças; nenhum histórico, segredo ou perfil pessoal distribuído.
- Testes do navegador incluído e de relocação; suíte offline ampliada para 40 casos e CI com Python 3.13.

## Refinamentos visuais — 17/10/2026

- Modalidades apresentadas como Análise simples e Análise avançada; nome do componente técnico removido da interface e das mensagens de resultado.
- Apresentação de registros antigos adaptada sem reescrever dados ou citações salvas.
- PDF redesenhado com capa, nota/indicadores, cores de estado, fontes incorporadas, tabelas e seções numeradas conforme o conteúdo disponível.
- Revisão visual da demonstração e de cenários sem nota, com cookies extensos e interpretação de IA simulada. Suíte de 37 testes mantida.

## 0.2.0 — 17/10/2026

- Painel de privacidade com nota acadêmica explicável, cobertura e evidências.
- Coleta Selenium local com sessão temporária e saída pública validada.
- Captura de página e inventário de cookies sem valores.
- Gemini opcional para interpretação de trechos, sem alterar a pontuação.
- Configuração local com chave de API volátil, progresso e controle de concorrência.
- PDF com nota, orientações, evidências, rubrica e limites.
- Documentação de metodologia, fontes, pesquisa de ferramentas e testes.

## 0.1.0 — 15/10/2026

- MVP Flask com coleta de HTML, HTTPS, heurísticas de banner/formulários/política, SQLite e PDF.
- Conferência posterior em 17/10: corrigida resposta para Host não autorizado.
