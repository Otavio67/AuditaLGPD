import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from auditalgpd import create_app
from auditalgpd.browser_worker import start_driver
from auditalgpd.portable import instance_lock
from auditalgpd.security import AuditError


class PortableTests(unittest.TestCase):
    def test_relocated_data_and_included_browser_without_saved_key(self):
        with tempfile.TemporaryDirectory(prefix="cópia portátil ") as temp:
            data = Path(temp) / "dados"
            with patch.dict(os.environ, {"AUDITALGPD_BROWSER_BINARY": "included.exe", "AUDITALGPD_BROWSER_DRIVER": "driver.exe", "GEMINI_API_KEY": ""}):
                app = create_app({"TESTING": True}, instance_path=str(data))
                client = app.test_client()
                self.assertEqual(app.config["DATABASE"], str(data / "auditorias.sqlite3"))
                settings = app.extensions["settings"]
                self.assertEqual(settings.browser, "chrome")
                settings.update("edge", "gemini-test", "temporary-test-key")
                self.assertEqual(settings.browser, "chrome")
                self.assertNotIn("temporary-test-key", (data / "preferences.json").read_text())
                response = client.get("/configuracoes")
                self.assertIn("Navegador de análise incluído".encode(), response.data)
                self.assertNotIn(b"temporary-test-key", response.data)
                self.assertEqual(client.get("/demonstracao").status_code, 200)

    def test_driver_uses_explicit_binaries_and_rejects_incomplete_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            binary, driver = Path(temp) / "browser.exe", Path(temp) / "driver.exe"
            binary.touch()
            driver.touch()
            with patch.dict(os.environ, {"AUDITALGPD_BROWSER_BINARY": str(binary), "AUDITALGPD_BROWSER_DRIVER": str(driver)}):
                webdriver, options = Mock(), Mock()
                options.arguments = ["--user-data-dir=" + str(Path(temp) / "profile")]
                start_driver(webdriver, options, "chrome")
                self.assertEqual(options.binary_location, str(binary))
                self.assertEqual(webdriver.Chrome.call_args.kwargs["service"].path, str(driver))
                self.assertEqual(webdriver.Chrome.call_args.kwargs["service"].env["TEMP"], temp)
                self.assertEqual(options.arguments, [])
                webdriver.Edge.assert_not_called()
                driver.unlink()
                with self.assertRaises(AuditError):
                    start_driver(webdriver, options, "chrome")

    def test_second_process_cannot_acquire_data_lock_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "application.lock"
            command = [sys.executable, "-c", "from pathlib import Path; from auditalgpd.portable import instance_lock; import sys\nwith instance_lock(Path(sys.argv[1])) as acquired: print(acquired)", str(path)]
            with instance_lock(path) as first:
                self.assertTrue(first)
                child = subprocess.run(command, capture_output=True, text=True, timeout=10, check=True)
                self.assertEqual(child.stdout.strip(), "False")
            child = subprocess.run(command, capture_output=True, text=True, timeout=10, check=True)
            self.assertEqual(child.stdout.strip(), "True")
