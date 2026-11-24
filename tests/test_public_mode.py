import tempfile
import unittest
from pathlib import Path
from auditalgpd import create_app
from auditalgpd.audit import Auditoria
from auditalgpd.security import Page

SECRET = "AIza-chave-de-teste-nao-real"


class NoFetch:
    def fetch(self, url, **kwargs):
        return Page(url, "<p>x</p>", True)


def build(directory, **config):
    app = create_app({"TESTING": True, "SECRET_KEY": "test-only", "DATABASE": str(Path(directory) / "t.db"),
                      "AUDITOR": Auditoria(NoFetch()), **config})
    app.extensions["settings"].api_key = SECRET
    return app, app.test_client()


class PublicModeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.directory.cleanup()

    def csrf(self, client):
        client.get("/")
        with client.session_transaction() as session:
            return session["csrf"]

    def test_locked_settings_refuse_changes_and_keep_the_key(self):
        app, client = build(self.directory.name, LOCK_SETTINGS=True)
        response = client.post("/configuracoes", data={"csrf": self.csrf(client), "browser": "edge", "model": "gemini-outro",
                                                         "api_key": "chave-do-visitante", "clear_key": "yes"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(app.extensions["settings"].api_key, SECRET)
        self.assertNotEqual(app.extensions["settings"].model, "gemini-outro")

    def test_locked_settings_page_is_read_only_and_never_shows_the_key(self):
        _, client = build(self.directory.name, LOCK_SETTINGS=True)
        page = client.get("/configuracoes")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Configura\xc3\xa7\xc3\xb5es bloqueadas", page.data)
        self.assertIn(b"<fieldset class=\"locked-fieldset\" disabled>", page.data)
        for path in ["/", "/configuracoes", "/historico"]:
            self.assertNotIn(SECRET.encode(), client.get(path).data)

    def test_unlocked_settings_still_work_locally(self):
        app, client = build(self.directory.name)
        response = client.post("/configuracoes", data={"csrf": self.csrf(client), "browser": "edge", "model": "gemini-teste", "api_key": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(app.extensions["settings"].model, "gemini-teste")
        self.assertNotIn(b"disabled>", client.get("/configuracoes").data.split(b"locked-fieldset")[1][:20])

    def test_gemini_checkbox_is_checked_by_default_only_when_configured_and_enabled(self):
        _, client = build(self.directory.name, AI_DEFAULT=True)
        home = client.get("/").data.decode()
        box = home[home.index('name="use_ai"'):].split(">")[0]
        self.assertIn("checked", box)
        self.assertNotIn("disabled", box)
        app, client = build(self.directory.name)
        box = client.get("/").data.decode()
        box = box[box.index('name="use_ai"'):].split(">")[0]
        self.assertNotIn("checked", box)
        app.extensions["settings"].api_key = ""
        app2, client2 = build(self.directory.name, AI_DEFAULT=True)
        app2.extensions["settings"].api_key = ""
        box = client2.get("/").data.decode()
        box = box[box.index('name="use_ai"'):].split(">")[0]
        self.assertIn("disabled", box)
        self.assertNotIn("checked", box)


if __name__ == "__main__":
    unittest.main()
