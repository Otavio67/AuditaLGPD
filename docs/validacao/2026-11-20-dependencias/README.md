# Validação — atualização de dependências (20/11/2026)

Ambiente: Windows 11, Python 3.12.14, ambiente virtual limpo instalado a partir do novo `requirements-lock.txt`.

## Versões alteradas

| Pacote | Antes | Depois |
|---|---|---|
| reportlab | 4.5.1 | 5.1.0 |
| pillow | 12.3.0 | 13.0.0 |
| soupsieve | 3.0.3 | 4.1.3 |
| selenium | 4.51.0 | 4.53.0 |
| trio | 0.34.0 | 0.35.0 |
| certifi | 2026.7.22 | 2026.10.23 |
| click | 8.5.0 | 8.5.1 |
| pycparser | 3.11 | 3.12 |

Em `pyproject.toml`, o limite do reportlab passou de `<5` para `<6`.

## Resultados

| Verificação | Resultado | Registro |
|---|---|---|
| `pip check` | Sem conflitos | [pip-check.txt](pip-check.txt) |
| Suíte offline (`unittest`) | 40/40 OK | [testes-unittest.txt](testes-unittest.txt) |
| Smoke do navegador real (Selenium + Edge) | OK | [smoke-navegador.txt](smoke-navegador.txt) |
| PDF da demonstração: reportlab 4 × 5 | 5 páginas nas duas versões. Páginas 2–5 idênticas pixel a pixel; na página 1 muda apenas o código aleatório do registro | [v4](relatorio-demo-reportlab4.pdf), [v5](relatorio-demo-reportlab5.pdf) |
| Interface (início, demonstração, configurações) | Renderização normal | prints abaixo |

## Prints

- [Tela inicial](tela-01-inicio.png)
- [Relatório de demonstração](tela-02-demonstracao.png)
- [Configurações](tela-03-configuracoes.png)
- PDF com reportlab 5: [p1](pdf-reportlab5-p1.png), [p2](pdf-reportlab5-p2.png), [p3](pdf-reportlab5-p3.png), [p4](pdf-reportlab5-p4.png), [p5](pdf-reportlab5-p5.png)
- PDF com reportlab 4, para comparação: [p1](pdf-reportlab4-p1.png)

O histórico não foi capturado porque pode conter análises reais. O pacote portátil não foi regenerado nesta validação.
