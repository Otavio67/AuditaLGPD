"""Entrada do pacote Windows; todos os caminhos são relativos à própria pasta."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import sys
import time
import urllib.request
import webbrowser


@contextmanager
def instance_lock(path):
    """O SO libera o bloqueio inclusive após encerramento forçado."""
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    pass
            yield acquired
        finally:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def running_url(path):
    """Confere a identidade da execução; não abre um serviço estranho na porta antiga."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(20):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            port, token = state["port"], state["token"]
            if type(port) is not int or not 1 <= port <= 65535 or not isinstance(token, str) or len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
                return None
            url = f"http://127.0.0.1:{port}/"
            with opener.open(url + "_portable/" + token, timeout=.5) as response:
                if response.read(100) == b"AuditaLGPD":
                    return url
        except (OSError, ValueError, KeyError, TypeError):
            pass
        time.sleep(.15)
    return None


def configure_bundle(root):
    binary = root / "browser/chrome-headless-shell-win64/chrome-headless-shell.exe"
    driver = root / "browser/chromedriver-win64/chromedriver.exe"
    if not binary.is_file() or not driver.is_file():
        raise RuntimeError("Faltam componentes. Use 'Extrair tudo' no ZIP antes de iniciar.")
    os.environ["AUDITALGPD_BROWSER_BINARY"] = str(binary)
    os.environ["AUDITALGPD_BROWSER_DRIVER"] = str(driver)
    os.environ["SE_AVOID_STATS"] = "true"
    os.environ["SE_OFFLINE"] = "true"
    # Evita gravar .pyc dentro dos componentes; não altera o Python instalado.
    sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description="AuditaLGPD portátil")
    parser.add_argument("--no-browser", action="store_true", help="Não abrir a interface automaticamente")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    configure_bundle(root)
    data = root / "dados"
    data.mkdir(exist_ok=True)
    state_path = data / "session.json"
    with instance_lock(data / "application.lock") as acquired:
        if not acquired:
            url = running_url(state_path)
            if url:
                print("O AuditaLGPD já está aberto em " + url, flush=True)
                if not args.no_browser:
                    webbrowser.open(url)
                return
            raise RuntimeError("O aplicativo já está iniciando. Aguarde alguns segundos e tente novamente.")
        from werkzeug.serving import make_server
        from auditalgpd import create_app
        app = create_app(instance_path=str(data))
        token = secrets.token_hex(16)

        @app.get("/_portable/" + token)
        def identify():
            return "AuditaLGPD", 200, {"Content-Type": "text/plain"}

        # Porta livre escolhida pelo SO; nunca expõe o servidor na rede local.
        server = make_server("127.0.0.1", 0, app, threaded=True)
        url = f"http://127.0.0.1:{server.server_port}/"
        state_path.write_text(json.dumps({"port": server.server_port, "token": token}), encoding="utf-8")
        print("\nAuditaLGPD pronto: " + url, flush=True)
        print("Mantenha esta janela aberta. Para encerrar, pressione Ctrl+C.\n", flush=True)
        if not args.no_browser:
            # A porta já está reservada; a primeira requisição aguarda serve_forever.
            import threading
            threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nAplicativo encerrado.")
        finally:
            app.extensions["jobs"].executor.shutdown(wait=True)
            server.server_close()
            state_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Não foi possível iniciar: " + str(exc), file=sys.stderr)
        sys.exit(1)
