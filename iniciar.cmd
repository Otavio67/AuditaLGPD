@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python nao encontrado. Siga a instalacao no README.md.
  pause
  exit /b 1
)
echo Abra http://127.0.0.1:5000/ no navegador.
echo Para encerrar, pressione Ctrl+C nesta janela.
".venv\Scripts\python.exe" -m flask --app auditalgpd run --host 127.0.0.1 --port 5000
pause
