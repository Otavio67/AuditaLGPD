import unittest
from auditalgpd.assessment import RULES, assessment, policy_topics, contextual_checks
from auditalgpd.detectors import parse_html
from auditalgpd.audit import Auditoria
from auditalgpd.domain import AuditResult, Check, Status
from auditalgpd.security import AuditError, Page


class StaticPage:
    def __init__(self, html):
        self.html = html

    def fetch(self, url, **kwargs):
        return Page(url, self.html, url.startswith("https"))


class AssessmentTests(unittest.TestCase):
    def test_low_coverage_gets_grade_capped_at_c_and_failed_collection_gets_none(self):
        result = assessment(AuditResult("https://example.org", checks=[Check("https", "HTTPS", Status.PRESENT, "ok")]))
        self.assertEqual(result["coverage"], 10)
        self.assertEqual(result["value"], 100)
        self.assertEqual(result["grade"], "C")
        self.assertTrue(result["capped"])
        failed = assessment(AuditResult("https://example.org", checks=[Check("collection", "Acesso", Status.ERROR, "x")]))
        self.assertIsNone(failed["value"])
        self.assertEqual(failed["grade"], "—")

    def test_site_without_policy_gets_low_grade_with_full_coverage(self):
        html = '<html><body><h1>Loja</h1><p>Bem-vindo</p></body></html>'
        result = Auditoria(StaticPage(html)).executar("http://example.org/")
        checks = {c.key: c.status for c in result.checks}
        self.assertEqual(checks["policy"], Status.ABSENT)
        self.assertEqual(checks["policy_content"], Status.ABSENT)
        self.assertEqual(checks["purposes"], Status.ABSENT)
        self.assertEqual(result.score["grade"], "E")
        self.assertEqual(result.score["value"], 0)
        self.assertGreaterEqual(result.score["coverage"], 75)

    def test_policy_page_itself_is_evaluated(self):
        html = ('<html><head><title>Política de Privacidade</title></head><body><h1>Política de Privacidade</h1>'
                '<p>A finalidade é prestar serviços. Coletamos nome e e-mail. Compartilhamos dados com parceiros. '
                'Os dados são armazenados por 5 anos. Seus direitos do titular incluem acesso e exclusão. '
                'O controlador é Exemplo Ltda, contato: dpo@example.org. Bases legais: execução de contrato.</p></body></html>')
        result = Auditoria(StaticPage(html)).executar("https://example.org/politica-de-privacidade/")
        checks = {c.key: c.status for c in result.checks}
        self.assertEqual(checks["policy"], Status.PRESENT)
        self.assertEqual(checks["policy_content"], Status.PRESENT)
        self.assertTrue(all(checks[k] == Status.PRESENT for k in ["purposes", "data_types", "sharing", "retention", "rights", "controller", "legal_basis"]))
        self.assertEqual(result.score["grade"], "A")

    def test_blocked_browser_falls_back_to_simple_analysis(self):
        class Blocked:
            def fetch(self, *args, **kwargs):
                raise AuditError("O site respondeu com HTTP 403 ao navegador automatizado.")
        result = Auditoria(StaticPage("<html><body><p>oi</p></body></html>"), browser_fetcher=Blocked()).executar("https://example.org/", mode="browser")
        checks = {c.key: c for c in result.checks}
        self.assertEqual(result.mode, "static")
        self.assertEqual(checks["selenium"].status, Status.ERROR)
        self.assertIn("análise simples", checks["selenium"].detail)
        self.assertNotIn("collection", checks)
        self.assertNotEqual(result.score["grade"], "—")

    def test_errors_are_not_scored_as_absences_and_weights_total_100(self):
        checks = [Check(key, title, Status.PRESENT, "ok") for key, title, _, _, _ in RULES]
        checks[0].status = Status.ERROR
        score = assessment(AuditResult("https://example.org", checks=checks))
        self.assertEqual(sum(r[3] for r in RULES), 100)
        self.assertEqual(score["value"], 100)
        self.assertEqual(score["coverage"], 90)
        self.assertFalse(score["missing"])

    def test_topics_have_literal_evidence_and_no_text_is_not_a_failure(self):
        text = "A finalidade é prestar o serviço. O controlador é Exemplo Ltda. Contato: privacidade@example.org."
        checks = {c.key: c for c in policy_topics(text)}
        self.assertEqual(checks["purposes"].status, Status.PRESENT)
        self.assertIn(checks["purposes"].evidence[0], text)
        self.assertEqual(checks["controller"].status, Status.PRESENT)
        self.assertTrue(all(c.status == Status.NOT_RUN for c in policy_topics("")))
        self.assertTrue(all(c.status == Status.ABSENT for c in policy_topics("", unavailable=Status.ABSENT)))

    def test_wordpress_policy_wording_for_retention_and_rights(self):
        text = ("Por quanto tempo mantemos os seus dados: o comentário e os seus metadados são conservados indefinidamente. "
                "Quais os seus direitos sobre seus dados: pode solicitar a remoção.")
        checks = {c.key: c.status for c in policy_topics(text)}
        self.assertEqual(checks["retention"], Status.PRESENT)
        self.assertEqual(checks["rights"], Status.PRESENT)
        footer = {c.key: c.status for c in policy_topics("Agência Exemplo © 2026 – Todos os direitos reservados.")}
        self.assertEqual(footer["rights"], Status.ABSENT)

    def test_banner_absence_and_no_form_are_pending_not_legal_failures(self):
        self.assertTrue(all(c.status == Status.NOT_RUN for c in contextual_checks(parse_html("<p>Olá</p>"), browser=True)))
        soup = parse_html('<div id="cookie-banner">Cookies <button>Aceitar</button><button>Rejeitar</button><button>Configurar</button></div>')
        self.assertEqual(contextual_checks(soup, browser=True)[1].status, Status.PRESENT)
        self.assertEqual(contextual_checks(soup, browser=False)[1].status, Status.NOT_RUN)

    def test_one_notice_does_not_approve_other_personal_forms(self):
        soup = parse_html('<form><input type="email"><a>Política de privacidade</a></form><form><input type="tel"></form>')
        self.assertEqual(contextual_checks(soup)[0].status, Status.ABSENT)
