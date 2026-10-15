# Arquitetura inicial

O MVP separa a interface Flask, a coleta HTTP, os detectores, a persistência SQLite e a geração de relatórios. Os estados das verificações distinguem presença, ausência, falha e não execução. Não será calculada uma porcentagem de conformidade jurídica.

Somente páginas públicas HTTP e HTTPS poderão ser consultadas. Endereços privados e locais serão rejeitados; os destinos de redirecionamentos também serão verificados. Não haverá envio de formulários nem navegação autenticada.

O escopo inicial é a página informada e, quando possível, uma política de privacidade vinculada a ela. Essa cobertura não representa a análise de todas as páginas de um domínio.
