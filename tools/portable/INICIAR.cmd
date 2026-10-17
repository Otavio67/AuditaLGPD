@echo off
setlocal
cd /d "%~dp0"
title AuditaLGPD
if not exist "%~dp0runtime\python.exe" (
  echo Extraia TODA a pasta do ZIP antes de iniciar o AuditaLGPD.
  pause
  exit /b 1
)
echo Iniciando AuditaLGPD. A interface abrira no navegador...
"%~dp0runtime\python.exe" -B -m auditalgpd.portable %*
if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar. Confira se toda a pasta foi extraida.
  pause
  exit /b 1
)
endlocal
