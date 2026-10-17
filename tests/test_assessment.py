import unittest
from auditalgpd.assessment import RULES, assessment, policy_topics, contextual_checks
from auditalgpd.detectors import parse_html
from auditalgpd.domain import AuditResult, Check, Status


class AssessmentTests(unittest.TestCase):
    def test_insufficient_collection_cannot_award_high_grade(self):
        result = assessment(AuditResult("https://example.org", checks=[Check("https", "HTTPS", Status.PRESENT, "ok")]))
        self.assertEqual(result["coverage"], 10)
        self.assertIsNone(result["value"])
        self.assertEqual(result["grade"], "—")

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

    def test_banner_absence_and_no_form_are_pending_not_legal_failures(self):
        self.assertTrue(all(c.status == Status.NOT_RUN for c in contextual_checks(parse_html("<p>Olá</p>"), browser=True)))
        soup = parse_html('<div id="cookie-banner">Cookies <button>Aceitar</button><button>Rejeitar</button><button>Configurar</button></div>')
        self.assertEqual(contextual_checks(soup, browser=True)[1].status, Status.PRESENT)
        self.assertEqual(contextual_checks(soup, browser=False)[1].status, Status.NOT_RUN)

    def test_one_notice_does_not_approve_other_personal_forms(self):
        soup = parse_html('<form><input type="email"><a>Política de privacidade</a></form><form><input type="tel"></form>')
        self.assertEqual(contextual_checks(soup)[0].status, Status.ABSENT)
