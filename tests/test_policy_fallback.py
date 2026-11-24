import unittest
from auditalgpd.assessment import assessment, contextual_checks
from auditalgpd.audit import common_policy_urls
from auditalgpd.detectors import parse_html
from auditalgpd.domain import AuditResult, Check, Status


class PolicyFallbackTests(unittest.TestCase):
    def test_common_paths_stay_on_the_same_origin(self):
        urls = common_policy_urls("https://exemplo.com.br:443/loja/inicio?x=1")
        self.assertIn("https://exemplo.com.br:443/politica-de-privacidade/", urls)
        self.assertTrue(all(u.startswith("https://exemplo.com.br:443/") for u in urls))

    def test_cookie_banner_with_some_controls_gets_partial_credit(self):
        soup = parse_html('<div id="cookie-banner">Cookies <button>Aceitar e fechar</button></div>')
        checks = contextual_checks(soup, browser=True)
        cookie = [c for c in checks if c.key == "cookie_choices"][0]
        self.assertEqual(cookie.status, Status.ABSENT)
        self.assertEqual(cookie.evidence, ["aceitar"])
        score = assessment(AuditResult("https://example.org", checks=[cookie]))
        item = [i for i in score["items"] if i["key"] == "cookie_choices"][0]
        self.assertEqual(item["partial"], 3)
        self.assertEqual(score["earned"], 3)

    def test_banner_with_all_controls_still_gets_full_credit(self):
        soup = parse_html('<div id="cookie-banner">Cookies <button>Aceitar</button><button>Rejeitar</button><button>Configurar</button></div>')
        cookie = [c for c in contextual_checks(soup, browser=True) if c.key == "cookie_choices"][0]
        score = assessment(AuditResult("https://example.org", checks=[cookie]))
        self.assertEqual(score["earned"], 10)


if __name__ == "__main__":
    unittest.main()
