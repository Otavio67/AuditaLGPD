# Pacote portátil Windows x64

O gerador `tools/build_portable.py` produz uma pasta e um ZIP que contêm a aplicação, o Python embeddable oficial 3.13.16, as dependências de `requirements-lock.txt` (mais colorama 0.4.6, dependência de console do Windows) e Chromium Headless Shell/ChromeDriver 155.0.8059.84. Não usa PyInstaller, ambiente virtual, Python do PATH ou instalação de pacotes na primeira abertura.

## Gerar

Em um Python com pip, a partir da raiz do repositório:

```powershell
python tools/build_portable.py --cache build/downloads --output dist
```

Use uma pasta de saída nova para cada build. O gerador não apaga pacotes anteriores. São necessários internet na preparação e espaço para os downloads, a pasta extraída e o ZIP. Os binários principais vêm de [Python.org](https://www.python.org/downloads/release/python-31316/) e [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/), com URLs versionadas e SHA-256 conferidos antes da extração. As bibliotecas são wheels de PyPI selecionadas para CPython 3.13/Windows x64.

O arquivo `manifest.json` registra versões, revisão do código, URLs, checksums dos downloads, wheels e arquivos distribuídos. Ao lado do ZIP é gerado um checksum SHA-256. Preserve as licenças: Python, bibliotecas, fontes Vera e os avisos completos do Chromium/ChromeDriver permanecem no pacote. `LICENCAS.txt` aponta para esses arquivos.

Só os arquivos `.py`, `.html`, `.css` e `.js` do pacote `auditalgpd`, os lançadores/guias e as dependências oficiais entram na distribuição. O gerador não copia `instance`, `.env`, `.venv`, `.git`, documentos do TCC, histórico, chaves, capturas pessoais ou perfis do navegador.

## Execução

- `INICIAR.cmd` usa caminhos relativos à pasta e abre o navegador padrão do Windows.
- `runtime/python313._pth` isola as importações nas bibliotecas e na aplicação incluídas; não ativa site-packages do usuário.
- O servidor escuta exclusivamente em `127.0.0.1`, em uma porta livre escolhida pelo sistema.
- Um bloqueio de arquivo mantido pelo sistema operacional impede duas execuções sobre os mesmos dados. A segunda abertura confere a identidade da sessão antes de abrir a interface existente.
- Os binários de análise são explícitos; não há download via Selenium Manager no portátil. ChromeDriver cria um perfil próprio dentro da pasta temporária da coleta, também removida pelo processo pai após timeout. Nenhum perfil pessoal é utilizado.
- O navegador de análise usa a mesma coleta, proxy público, TLS e limites da versão de desenvolvimento. O Headless Shell tem diferenças em relação ao Chrome completo; não há promessa de equivalência de renderização em todos os sites.
- Histórico e preferências vão para `dados`. Chaves digitadas na interface continuam somente em memória. Não há chave Gemini distribuída.

O launcher portátil é específico para a estrutura gerada; para executar o código-fonte, use o fluxo de instalação do README. Windows ARM/32 bits, Linux e macOS precisam de distribuições próprias e não são alvos deste ZIP.

## Validação

```powershell
python tools/smoke_portable.py dist/AuditaLGPD-Portable-Windows-x64.zip --destination "build/cópia de teste"
```

Esse teste extrai uma cópia nova, verifica os hashes e a ausência de dados pessoais, limita o PATH ao sistema, invalida PYTHONHOME/PYTHONPATH e inicia o `.cmd` real. Confere interface, instância única, duas análises reais em example.com, SQLite, captura e PDF. Não usa Gemini. A árvore de processos criada pelo teste é encerrada no final; outros servidores locais são preservados. Os dados do teste ficam na cópia, sem alterar o ZIP.

Teste adicional do navegador, com transporte de fixture injetado exclusivamente pelo teste:

```powershell
dist/AuditaLGPD-Portable/runtime/python.exe -B tools/smoke_browser.py --portable dist/AuditaLGPD-Portable
```

Confere JavaScript real, aviso e controles de consentimento, cookie fictício, captura e remoção de valores. A suíte offline também cobre instância única entre processos, diretório de dados relocável, chave fora do disco e seleção explícita dos binários. A matriz do CI inclui Python 3.13, além de 3.11/3.12.

Testar uma cópia em outro diretório na mesma máquina verifica relocação e independência do Python instalado; não substitui uma validação em outro computador ou em todas as versões/configurações do Windows.
