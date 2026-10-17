import json
import tempfile
import unittest
from pathlib import Path
from auditalgpd.gemini import GeminiClient, TOPICS
from auditalgpd.settings import Settings
from auditalgpd.security import AuditError


class GeminiTests(unittest.TestCase):
    def response(self, quote="A finalidade é prestar o serviço."):
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({"temas": [
            {"chave": k, "estado": "identificado" if k == "purposes" else "nao_localizado", "citacao": quote if k == "purposes" else "", "explicacao": "Descrição do tema."}
            for k in TOPICS]})}]}}]}

    def test_fixed_endpoint_key_header_redaction_and_no_score_from_ai(self):
        requests = []
        client = GeminiClient("fake-test-key", transport=lambda req: requests.append(req) or self.response())
        result = client.analyze("A finalidade é prestar o serviço. Contato ana@example.org CPF 123.456.789-01", "https://example.org/privacy")
        request = requests[0]
        self.assertNotIn("fake-test-key", request.full_url)
        self.assertTrue(request.full_url.startswith("https://generativelanguage.googleapis.com/"))
        self.assertNotIn(b"ana@example.org", request.data)
        self.assertNotIn(b"123.456.789-01", request.data)
        self.assertEqual(result["items"][0]["status"], "identificado")
        self.assertNotIn("score", result)

    def test_fabricated_evidence_is_discarded(self):
        result = GeminiClient("fake", transport=lambda _: self.response("Texto inventado")).analyze("A finalidade é prestar o serviço.", "https://example.org/")
        self.assertEqual(result["items"][0]["status"], "incerto")
        self.assertEqual(result["items"][0]["quote"], "")

    def test_invalid_schema_and_missing_key_do_not_succeed(self):
        for client in [GeminiClient(), GeminiClient("fake", transport=lambda _: {}), GeminiClient("fake", model="../malicious")]:
            with self.assertRaises(AuditError):
                client.analyze("Texto de política.", "https://example.org")

    def test_ui_key_is_never_written_to_preferences(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Settings(temp)
            settings.update("edge", "gemini-3.5-flash-lite", "fake-private-test-key")
            self.assertTrue(settings.public()["configured"])
            self.assertNotIn("fake-private-test-key", (Path(temp)/"preferences.json").read_text())
            self.assertNotIn("api_key", settings.public())
