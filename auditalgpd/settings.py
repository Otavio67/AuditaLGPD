"""Preferências locais; a chave informada na interface fica apenas na memória."""

import json
import os
from pathlib import Path
import re
from .security import AuditError
from .gemini import GeminiClient


class Settings:
    def __init__(self, directory):
        self.path = Path(directory) / "preferences.json"
        try:
            preferences = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            preferences = {}
        self.bundled = bool(os.environ.get("AUDITALGPD_BROWSER_BINARY") and os.environ.get("AUDITALGPD_BROWSER_DRIVER"))
        self.browser = "chrome" if self.bundled else preferences.get("browser", "edge")
        self.model = preferences.get("model", os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"))
        self.api_key = os.environ.get("GEMINI_API_KEY", "")

    def update(self, browser, model, key="", clear=False):
        if browser not in {"edge", "chrome"} or not re.fullmatch(r"gemini-[a-zA-Z0-9._-]{1,80}", model):
            raise AuditError("Escolha Edge/Chrome e informe um identificador de modelo Gemini válido.")
        if len(key) > 250 or any(ord(c) < 32 for c in key):
            raise AuditError("O formato da chave não foi aceito.")
        browser = "chrome" if self.bundled else browser
        self.browser, self.model = browser, model
        if clear:
            self.api_key = ""
        elif key:
            self.api_key = key
        self.path.write_text(json.dumps({"browser": browser, "model": model}), encoding="utf-8")

    def client(self):
        return GeminiClient(self.api_key, self.model)

    def public(self):
        return {"browser": self.browser, "model": self.model, "configured": bool(self.api_key), "bundled": self.bundled}
