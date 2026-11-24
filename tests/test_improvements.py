import unittest
from auditalgpd.assessment import assessment, grade_for
from auditalgpd.domain import AuditResult, Check, Status


class ImprovementTests(unittest.TestCase):
    def low_score(self):
        checks = [Check("https", "HTTPS", Status.PRESENT, "ok"),
                  Check("policy", "Link", Status.ABSENT, "sem link"),
                  Check("cookie_choices", "Cookies", Status.ABSENT, "só aceitar", ["aceitar"]),
                  Check("form_notice", "Forms", Status.ABSENT, "sem aviso")]
        return assessment(AuditResult("https://example.org", checks=checks))

    def test_improvements_are_ordered_by_point_gain(self):
        score = self.low_score()
        self.assertEqual([i["key"] for i in score["improvements"]], ["form_notice", "policy", "cookie_choices"])
        self.assertEqual([i["gain"] for i in score["improvements"]], [10, 10, 7])
        self.assertEqual([i["severity"] for i in score["improvements"]], ["alta", "alta", "media"])

    def test_partial_credit_reduces_the_gain_of_cookie_choices(self):
        item = [i for i in self.low_score()["improvements"] if i["key"] == "cookie_choices"][0]
        self.assertEqual(item["weight"], 10)
        self.assertEqual(item["gain"], 7)
        self.assertEqual(item["evidence"], ["aceitar"])

    def test_potential_grade_assumes_every_listed_item_is_fixed(self):
        score = self.low_score()
        self.assertEqual((score["value"], score["grade"]), (13, "E"))
        self.assertEqual(score["potential"], {"value": 40, "grade": "D", "gain": 27})

    def test_no_improvements_when_nothing_is_missing(self):
        score = assessment(AuditResult("https://example.org", checks=[Check("https", "HTTPS", Status.PRESENT, "ok")]))
        self.assertEqual(score["improvements"], [])
        self.assertEqual(score["potential"]["gain"], 0)

    def test_grade_scale(self):
        self.assertEqual([grade_for(v) for v in (95, 80, 65, 50, 10, None)], ["A", "B", "C", "D", "E", "—"])


if __name__ == "__main__":
    unittest.main()
