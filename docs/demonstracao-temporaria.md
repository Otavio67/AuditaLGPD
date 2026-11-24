# Demonstração temporária com link público

Para a apresentação do TCC, o app roda no seu computador e um túnel da Cloudflare gera um link público enquanto a janela estiver aberta. Nada fica hospedado em servidor.

## Antes

- Instale o cloudflared: `winget install --id Cloudflare.cloudflared`.
- O ambiente Python do README precisa estar criado (`.venv`).
- Mantenha o computador ligado e com internet durante a apresentação.

## Subir

```powershell
.\.venv\Scripts\python.exe tools\publicar_tcc.py
```

O script pede um código de acesso (Enter gera um aleatório), inicia o app em `127.0.0.1:5000` e mostra o link `https://...trycloudflare.com`. Envie o link e o código à banca.

## Controles

- Quem acessa o link precisa digitar o código. Dez tentativas erradas em dez minutos bloqueiam novas tentativas por um tempo.
- O limite de análises por hora fica em `AUDITALGPD_MAX_ANALYSES_PER_HOUR` (padrão 100 no script). Ele é contado em memória e zera ao reiniciar.
- Para encerrar, pressione `Ctrl+C` na janela. O link deixa de funcionar.

## Limites

- O link muda a cada execução e não tem garantia de disponibilidade. É um recurso de demonstração, não de produção.
- O app continua sem autenticação de usuários. O código de acesso só protege a apresentação.

## Link fixo (ngrok)

Com o ngrok instalado e o token configurado (`ngrok config add-authtoken ...`), o script usa o domínio gratuito fixo da sua conta e gera o QR code a partir dele. O domínio é lido da variável `NGROK_DOMAIN` (do ambiente ou das variáveis do usuário do Windows) e não fica gravado no código. Defina uma vez, com o domínio que aparece em Domains no painel do ngrok:

```powershell
setx NGROK_DOMAIN seu-dominio.ngrok-free.dev
```

Sem `NGROK_DOMAIN` ou sem o token, o script usa o túnel Cloudflare. O mesmo endereço serve para qualquer apresentação, então o banner impresso não precisa mudar. Sem o token, o script volta ao túnel Cloudflare com link aleatório.

No plano gratuito, o navegador mostra uma página de aviso do ngrok antes do site; basta clicar em "Visit Site". O link só funciona enquanto o script estiver rodando. Requer ngrok 3.2x ou mais novo para o parâmetro `--url` (`ngrok update`).

## Gemini conectado na demonstração

Ao rodar `publicar_tcc.py`, o script pergunta a chave do Gemini com a digitação oculta (ou usa a variável de ambiente `GEMINI_API_KEY`, se já existir). A chave fica só na memória do app durante a apresentação: não é gravada em arquivo, não aparece no relatório e não vai para o GitHub. Com a chave informada:

- a opção "Incluir interpretação com Gemini" já vem marcada na tela inicial;
- a página de Configurações fica bloqueada, para que visitantes não troquem nem removam a chave;
- cada análise com IA usa a cota (e o eventual custo) da sua conta Google, e o texto da política analisada (até 24 mil caracteres, com remoção básica de e-mail, CPF e telefone) é enviado ao Google.

Para rodar sem Gemini, pressione Enter na pergunta da chave ou use `--sem-gemini`. Depois da apresentação, vale revogar a chave no Google AI Studio se ela foi compartilhada em algum lugar.

## Dicas do Gemini no painel "Como melhorar a nota"

Com a IA marcada e nota abaixo de 60, o Gemini escreve uma dica por critério, com base no que foi observado no site e em referências da LGPD de uma lista fixa. O painel mostra um aviso destacado dizendo que parte do texto foi escrita com ajuda de IA, que ela pode errar e que a nota não é alterada por ela. Se o Gemini falhar, o relatório sai normalmente com as orientações padrão e uma nota explicando o motivo.

- Cada análise com IA pode usar até duas chamadas: interpretação da política (quando há texto) e dicas de melhoria (só nota baixa).
- O plano gratuito tem limites por minuto e por dia (erro 429). Teste a chave no dia anterior e evite muitas análises seguidas antes da apresentação.
- O Google às vezes responde "alta demanda" (503). O app troca de modelo sozinho e tenta de novo uma vez; se ainda assim falhar, mostra o aviso no painel.

## Gemini: uma chamada por análise e cache

- Cada análise com IA faz **uma única chamada**: a leitura da política e as dicas de melhoria vão juntas (antes eram duas).
- O contexto enviado ficou mais rico: nomes dos cookies (sem valores), tipos de campo dos formulários, serviços de terceiros, controles encontrados no aviso de cookies e o que a leitura da política achou, com trechos curtos e remoção básica de e-mails, CPFs e telefones.
- As respostas válidas ficam em cache por 24 horas em `instance/ai_cache.sqlite3`. O cache é por site, texto da política, critérios e campos de formulário. Repetir a análise do mesmo site não gasta cota, e a tela avisa quando a resposta foi reaproveitada. Para limpar, apague esse arquivo.
- A cota gratuita é **por modelo**. Se um modelo ficar sem cota ou sobrecarregado, o app tenta os modelos reserva (`GEMINI_FALLBACK_MODELS`) antes de desistir.
