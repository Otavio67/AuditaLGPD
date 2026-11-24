"""Demonstração temporária: sobe o AuditaLGPD neste PC e um túnel Cloudflare.

Uso (a partir da raiz do projeto, com o .venv criado conforme o README):
    .\\.venv\\Scripts\\python.exe tools\\publicar_tcc.py

O app continua escutando só em 127.0.0.1; o cloudflared abre uma conexão de saída
e gera um endereço https://...trycloudflare.com enquanto esta janela estiver aberta.
Ctrl+C encerra o app e o túnel.
"""

import getpass
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
PORT = 5000
# O domínio fixo do ngrok vem da variável NGROK_DOMAIN (ambiente ou variáveis do usuário do Windows); não fica no código.
LIMIT_PER_HOUR = os.environ.get("AUDITALGPD_MAX_ANALYSES_PER_HOUR", "100")
CLOUDFLARED_CANDIDATES = [
    shutil.which("cloudflared"),
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
]


def user_env(name):
    """Variável do ambiente ou, no Windows, das variáveis do usuário (setx). Terminais abertos antes do setx não a herdam."""
    value = os.environ.get(name, "").strip()
    if value or os.name != "nt":
        return value
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return str(winreg.QueryValueEx(key, name)[0]).strip()
    except OSError:
        return ""


def find_cloudflared():
    for candidate in CLOUDFLARED_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("cloudflared não encontrado. Instale com: winget install --id Cloudflare.cloudflared")


def find_ngrok():
    """Usa o ngrok só se estiver instalado e com token configurado; caso contrário, cai no Cloudflare."""
    candidates = [shutil.which("ngrok")]
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    candidates += [str(p) for p in base.glob("Ngrok.Ngrok_*/ngrok.exe")]
    config = Path(os.environ.get("LOCALAPPDATA", "")) / "ngrok" / "ngrok.yml"
    try:
        has_token = "authtoken" in config.read_text(encoding="utf-8")
    except OSError:
        has_token = bool(os.environ.get("NGROK_AUTHTOKEN"))
    if not has_token:
        return None
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def read_plain_output(stream):
    for line in stream:
        print("[tunel] " + line.rstrip(), flush=True)


def make_qr(url):
    """Gera PNG local com o link; o endereço não sai do computador."""
    import qrcode
    path = ROOT / "demonstracao-qr.png"
    qrcode.make(url).save(path)
    print(f"QR code salvo em: {path}", flush=True)
    if os.name == "nt":
        os.startfile(path)


def read_tunnel_output(stream):
    for line in stream:
        print("[tunel] " + line.rstrip(), flush=True)
        match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if match:
            print("\n=== LINK PARA A BANCA: " + match.group(0) + " ===\n", flush=True)
            try:
                make_qr(match.group(0))
            except Exception as exc:
                print("Não foi possível gerar o QR code: " + str(exc), flush=True)


def main():
    no_code = "--sem-codigo" in sys.argv[1:]
    if no_code:
        code = ""
    else:
        typed = input("Código de acesso para a banca (Enter gera um aleatório): ").strip()
        code = typed or secrets.token_urlsafe(6)
    # A chave do Gemini vem do ambiente ou é digitada aqui (oculta). Fica só na memória do app: nunca vai a arquivo.
    gemini_key = user_env("GEMINI_API_KEY")
    if not gemini_key and "--sem-gemini" not in sys.argv[1:] and sys.stdin.isatty():
        gemini_key = getpass.getpass("Chave do Gemini (Enter para não usar; a digitação fica oculta e a chave não é salva): ").strip()
    # Configurações travadas: visitantes não podem trocar nem remover a chave.
    env = dict(os.environ, AUDITALGPD_ACCESS_CODE=code, AUDITALGPD_MAX_ANALYSES_PER_HOUR=LIMIT_PER_HOUR, AUDITALGPD_LOCK_SETTINGS="1")
    if gemini_key:
        env.update(GEMINI_API_KEY=gemini_key, AUDITALGPD_AI_DEFAULT="1")
        if user_env("GEMINI_MODEL"):
            env["GEMINI_MODEL"] = user_env("GEMINI_MODEL")
    env.setdefault("PYTHONUNBUFFERED", "1")
    app = subprocess.Popen([sys.executable, "-m", "flask", "--app", "auditalgpd", "run",
                            "--host", "127.0.0.1", "--port", str(PORT)], cwd=ROOT, env=env)
    time.sleep(3)
    ngrok_domain = user_env("NGROK_DOMAIN")
    ngrok = find_ngrok() if ngrok_domain else None
    if ngrok:
        # Link fixo (gratuito): o mesmo endereço e o mesmo QR code valem em toda apresentação.
        link = "https://" + ngrok_domain
        tunnel = subprocess.Popen([ngrok, "http", str(PORT), "--url", link, "--host-header", "127.0.0.1", "--log", "stdout"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=read_plain_output, args=(tunnel.stdout,), daemon=True).start()
        print("\n=== LINK FIXO PARA A BANCA: " + link + " ===\n", flush=True)
        try:
            make_qr(link)
        except Exception as exc:
            print("Não foi possível gerar o QR code: " + str(exc), flush=True)
    else:
        tunnel = subprocess.Popen([find_cloudflared(), "tunnel", "--url", f"http://127.0.0.1:{PORT}",
                                   "--http-host-header", "127.0.0.1"], stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=read_tunnel_output, args=(tunnel.stdout,), daemon=True).start()
    print(f"\nCódigo de acesso: {code}" if code else "\nSem código de acesso: qualquer pessoa com o link pode usar o app.")
    print(f"Limite: {LIMIT_PER_HOUR} análises por hora.")
    print("Gemini: conectado e marcado por padrão." if gemini_key else "Gemini: desativado (sem chave).")
    print("Mantenha esta janela aberta. Ctrl+C encerra o app e o túnel.\n", flush=True)
    try:
        app.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (tunnel, app):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    main()
