"""Coleta Selenium em processo separado com prazo e perfil descartável."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from .security import AuditError, Page, normalize_url, resolve_public


class SeleniumFetcher:
    def __init__(self, cache_dir, browser="edge"):
        self.cache_dir = Path(cache_dir)
        self.browser = browser

    def fetch(self, url, deadline=None, origin=None):
        target = normalize_url(url)
        if origin and (target.scheme, target.host, target.port) != origin:
            raise AuditError("A política está fora da origem da página.")
        resolve_public(target.host, target.port)
        remaining = min(65, (deadline or time.monotonic()+65) - time.monotonic())
        if remaining < 8:
            raise AuditError("O tempo limite da coleta dinâmica foi atingido.")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="audit-browser-") as temp:
            config = Path(temp) / "input.json"
            output = Path(temp) / "output.json"
            config.write_text(json.dumps({"url": target.url, "browser": self.browser, "timeout": max(5, remaining-5),
                                          "profile": str(Path(temp)/"profile"), "output": str(output), "origin": origin}), encoding="utf-8")
            environment = dict(os.environ)
            environment.update(SE_CACHE_PATH=str(self.cache_dir), SE_AVOID_STATS="true", SE_TIMEOUT="35", NO_PROXY="localhost,127.0.0.1")
            for key in list(environment):
                if key.lower() in {"http_proxy", "https_proxy", "all_proxy"}:
                    environment.pop(key)
            process = subprocess.Popen([sys.executable, "-m", "auditalgpd.browser_worker", str(config)],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       env=environment, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                       start_new_session=os.name != "nt")
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
                raise AuditError("O navegador excedeu o prazo da análise e foi encerrado.")
            if not output.exists() or output.stat().st_size > 4_000_000:
                raise AuditError("A análise avançada não foi concluída. Confira o navegador selecionado nas configurações.")
            try:
                data = json.loads(output.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                raise AuditError("O navegador retornou uma resposta inválida.") from exc
            if "error" in data:
                raise AuditError(data["error"])
            final = normalize_url(data["url"])
            if origin and (final.scheme, final.host, final.port) != origin:
                raise AuditError("A política saiu da origem permitida.")
            return Page(final.url, data["html"], data["tls_verified"], data["browser"])
