import tempfile
import unittest
from pathlib import Path
from auditalgpd.storage import Repository
from auditalgpd.domain import AuditResult, Check, Status


class StorageTests(unittest.TestCase):
    def test_round_trip_and_parameterized_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Repository(str(Path(directory) / "test.db"))
            result = AuditResult("https://example.com/", checks=[Check("https", "HTTPS", Status.PRESENT, "Certificado validado")])
            store.save(result)
            self.assertEqual(store.get(result.id).to_dict(), result.to_dict())
            self.assertEqual(len(store.latest()), 1)
            self.assertIsNone(store.get("' OR 1=1 --"))
