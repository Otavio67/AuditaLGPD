"""Teste opt-in de uma CÓPIA do portátil. Faz duas consultas a example.com.

Verifica o launcher real, isolamento do Python, instância única, coleta
simples/avançada, persistência, captura e PDF. Não executa chamadas ao Gemini.
O pacote original permanece intacto. Use --destination com uma pasta nova.
"""

import argparse
import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit("Escolha uma pasta nova para preservar testes anteriores.")
    destination.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive:
        for name in archive.namelist():
            assert (destination / name).resolve().is_relative_to(destination)
        archive.extractall(destination)
    bundle = destination / "AuditaLGPD-Portable"
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        with (bundle / name).open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == expected, name
    assert not list((bundle / "dados").iterdir()), "O pacote original contém dados de execução."
    assert not any(p.name in {".env", ".venv", ".git", "preferences.json"} for p in bundle.rglob("*"))
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith(("GEMINI_", "AUDITALGPD_", "SE_"))}
    environment.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"),
                       PYTHONHOME="X:/python-inexistente", PYTHONPATH="X:/bibliotecas-inexistentes")
    command = [str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe"), "/d", "/c", "INICIAR.cmd", "--no-browser"]
    output = (destination / "execucao.log").open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=bundle, env=environment, stdout=output, stderr=subprocess.STDOUT)
    try:
        state_path = bundle / "dados/session.json"
        deadline = time.monotonic() + 25
        while not state_path.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(.2)
        assert state_path.exists(), "O launcher não criou a sessão. Confira execucao.log."
        state = json.loads(state_path.read_text(encoding="utf-8"))
        base = f"http://127.0.0.1:{state['port']}/"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(CookieJar()))

        def get(path):
            return opener.open(base + path, timeout=150).read()

        for page in ["", "health", "demonstracao", "historico", "configuracoes"]:
            assert get(page), page
        assert "Navegador de análise incluído".encode() in get("configuracoes")
        second = subprocess.run(command, cwd=bundle, env=environment, capture_output=True, timeout=12)
        assert second.returncode == 0, second.stderr.decode(errors="replace")
        assert str(state["port"]).encode() in second.stdout
        assert json.loads(state_path.read_text()) == state, "A segunda abertura substituiu a execução."
        for mode in ["static", "browser"]:
            token = re.search(rb'name="csrf" value="([^"]+)"', get(""))[1].decode()
            data = urllib.parse.urlencode({"csrf": token, "authorized": "yes", "url": "https://example.com/", "mode": mode}).encode()
            request = urllib.request.Request(base + "auditorias", data=data)
            with opener.open(request, timeout=150) as response:
                url = response.url
                assert "/auditorias/" in url, url
                assert response.status == 200
            pdf = opener.open(url + "/relatorio.pdf", timeout=30).read()
            assert pdf.startswith(b"%PDF-") and len(pdf) > 20_000
            if mode == "browser":
                screenshot = opener.open(url + "/captura.png", timeout=15).read()
                assert screenshot.startswith(b"\x89PNG")
        with sqlite3.connect(bundle / "dados/auditorias.sqlite3") as db:
            rows = db.execute("SELECT payload FROM audits").fetchall()
        assert len(rows) == 2
        for (payload,) in rows:
            result = json.loads(payload)
            assert result["checks"][0]["status"] == "presente", result["checks"][0]
            assert not any(c["status"] == "erro" for c in result["checks"]), result["checks"]
        print("OK: ZIP íntegro/sem dados pessoais; launcher em pasta com espaços/acentos; Python próprio com PATH isolado; instância única; análises simples/avançada; SQLite; PNG e PDF.")
        print("Cópia de teste e registro: " + str(destination))
    finally:
        # Encerra somente a árvore que este teste iniciou; não toca no app pessoal.
        subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"), "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
        process.wait(timeout=10)
        output.close()


if __name__ == "__main__":
    main()
