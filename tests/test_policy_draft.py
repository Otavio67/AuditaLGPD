import tempfile
import unittest
from pathlib import Path
from auditalgpd import create_app
from auditalgpd.assessment import RULES, assessment
from auditalgpd.audit import Auditoria
from auditalgpd.domain import AuditResult, Check, Status
from auditalgpd.policy_draft import build_policy_draft, eligible, filename
from auditalgpd.security import Page


class NoFetch:
    def fetch(self, url, **kwargs):
        return Page(url, "<p>x</p>", True)


def low_audit(url, forms=None, cookies=None, domains=None):
    checks = [Check("https", "Conexão HTTPS", Status.PRESENT, "ok"),
              Check("policy", "Link de política", Status.ABSENT, "sem link"),
              Check("form_notice", "Informação próxima ao formulário", Status.ABSENT, "sem aviso"),
              Check("forms", "Formulários de dados pessoais", Status.PRESENT if forms else Status.ABSENT, "x",
                    [f"Campos com indícios de dados pessoais: {forms}."] if forms else [])]
    audit = AuditResult(url, final_url=url, checks=checks, mode="browser",
                        browser={"cookies": cookies or [], "domains": domains or []})
    audit.score = assessment(audit)
    return audit


class PolicyDraftTests(unittest.TestCase):
    def test_draft_changes_with_the_site(self):
        cookies = [{"name": "_ga", "domain": ".loja.com.br", "secure": False, "httpOnly": False, "sameSite": "Lax"},
                   {"name": "_fbp", "domain": ".loja.com.br", "secure": False, "httpOnly": False, "sameSite": "Lax"}]
        rich = low_audit("https://www.loja.com.br/", "email, identificação/contato", cookies, ["www.google-analytics.com", "connect.facebook.net", "cdn.exemplo-estranho.io"])
        plain = low_audit("https://www.simples.org/")
        a, b = build_policy_draft(rich, rich.score), build_policy_draft(plain, plain.score)
        self.assertIn("loja.com.br", a)
        self.assertIn("e-mail, nome e dados de contato", a)
        self.assertIn("_ga (.loja.com.br): Estatística - Google Analytics", a)
        self.assertIn("_fbp (.loja.com.br): Publicidade - Meta", a)
        self.assertIn("Google (análise de audiência", a)
        self.assertIn("cdn.exemplo-estranho.io", a)
        self.assertIn("TEXTO CURTO PARA COLOCAR AO LADO DO FORMULÁRIO", a)
        self.assertIn("simples.org", b)
        self.assertNotIn("_ga", b)
        self.assertNotIn("TEXTO CURTO PARA COLOCAR AO LADO DO FORMULÁRIO", b)
        self.assertNotEqual(a, b)

    def test_draft_lists_what_the_analysis_missed_and_keeps_placeholders(self):
        audit = low_audit("https://www.simples.org/")
        text = build_policy_draft(audit, audit.score)
        self.assertIn("O QUE A ANÁLISE APONTOU", text)
        self.assertIn("- Link de política:", text)
        self.assertIn("[NOME EMPRESARIAL]", text)
        self.assertIn("não é consultoria jurídica", text)

    def test_eligibility_and_filename(self):
        self.assertTrue(eligible({"value": 59}))
        self.assertFalse(eligible({"value": 60}))
        self.assertFalse(eligible({"value": None}))
        self.assertEqual(filename(low_audit("https://www.Loja.com.br/x")), "politica-de-privacidade-loja.com.br.txt")


class PolicyRouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-only", "DATABASE": str(Path(self.directory.name) / "t.db"),
                               "AUDITOR": Auditoria(NoFetch())})
        self.client = self.app.test_client()
        repo = self.app.extensions["repository"]
        self.low = low_audit("https://www.loja.com.br/", "email")
        repo.save(self.low)
        checks = [Check(key, title, Status.PRESENT, "ok") for key, title, _, _, _ in RULES]
        self.high = AuditResult("https://ok.example.org/", final_url="https://ok.example.org/", checks=checks)
        self.high.score = assessment(self.high)
        repo.save(self.high)

    def tearDown(self):
        self.directory.cleanup()

    def token(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            return session["csrf"]

    def test_download_for_low_score_is_a_text_attachment(self):
        response = self.client.post(f"/auditorias/{self.low.id}/politica", data={"csrf": self.token()})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["Content-Type"])
        self.assertIn("politica-de-privacidade-loja.com.br.txt", response.headers["Content-Disposition"])
        self.assertIn("RASCUNHO DE POLÍTICA DE PRIVACIDADE".encode(), response.data)

    def test_refused_without_csrf_for_high_score_and_unknown_audit(self):
        self.assertEqual(self.client.post(f"/auditorias/{self.low.id}/politica").status_code, 400)
        self.assertEqual(self.client.post(f"/auditorias/{self.high.id}/politica", data={"csrf": self.token()}).status_code, 403)
        self.assertEqual(self.client.post("/auditorias/nao-existe/politica", data={"csrf": self.token()}).status_code, 404)
        self.assertEqual(self.client.get(f"/auditorias/{self.low.id}/politica").status_code, 405)

    def test_button_only_appears_for_low_scores(self):
        self.assertIn("Gerar rascunho da política".encode(), self.client.get(f"/auditorias/{self.low.id}").data)
        self.assertNotIn("Gerar rascunho da política".encode(), self.client.get(f"/auditorias/{self.high.id}").data)
        self.assertNotIn("Gerar rascunho da política".encode(), self.client.get("/demonstracao").data)


if __name__ == "__main__":
    unittest.main()
