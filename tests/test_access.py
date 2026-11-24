import tempfile
import unittest
from pathlib import Path
from auditalgpd import create_app
from auditalgpd.audit import Auditoria
from auditalgpd.web import within_hourly_limit


class FixtureFetcher:
    def fetch(self, url, **kwargs):
        raise AssertionError("A coleta não deve ocorrer nestes testes.")


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-only", "ACCESS_CODE": "apresentacao-2026",
                               "DATABASE": str(Path(self.directory.name) / "test.db"), "AUDITOR": Auditoria(FixtureFetcher())})
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def csrf(self):
        self.client.get("/entrar")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def test_pages_require_code_but_health_stays_open(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertIn("/entrar", self.client.get("/").headers["Location"])
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_wrong_code_is_refused_and_right_code_opens_the_app(self):
        wrong = self.client.post("/entrar", data={"codigo": "errado", "csrf": self.csrf()})
        self.assertEqual(wrong.status_code, 200)
        self.assertIn("Código incorreto".encode(), wrong.data)
        self.assertEqual(self.client.get("/").status_code, 302)
        right = self.client.post("/entrar", data={"codigo": "apresentacao-2026", "csrf": self.csrf()})
        self.assertEqual(right.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_repeated_wrong_codes_are_throttled(self):
        for _ in range(10):
            self.client.post("/entrar", data={"codigo": "errado", "csrf": self.csrf()})
        blocked = self.client.post("/entrar", data={"codigo": "apresentacao-2026", "csrf": self.csrf()})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Muitas tentativas".encode(), blocked.data)

    def test_hourly_limit_counts_only_when_enabled(self):
        with self.app.app_context():
            self.app.config["MAX_ANALYSES_PER_HOUR"] = 0
            self.assertTrue(all(within_hourly_limit() for _ in range(5)))
            self.app.config["MAX_ANALYSES_PER_HOUR"] = 2
            self.app.extensions["recent_analyses"].clear()
            self.assertEqual([within_hourly_limit() for _ in range(3)], [True, True, False])


if __name__ == "__main__":
    unittest.main()
