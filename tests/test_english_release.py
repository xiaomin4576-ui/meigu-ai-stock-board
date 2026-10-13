import json
import hashlib
import base64
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cryptography.exceptions import InvalidTag
from english_release import install, package, verify, envelope, refresh_runtime, english_gate, RUNTIME


class EnglishReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = '<a href="/">Home</a><script id="course-data" type="application/json">' + json.dumps({
            "units": [{"id": "test-lesson", "title": "Private lesson content"}],
            "quiz": [{"id": "stable-question-id"}],
        }) + '</script>'
        cls.gate = package(cls.source, "temporary-test-password")

    def test_round_trip_preserves_ids_and_hides_content(self):
        data = verify(self.gate, "temporary-test-password")
        self.assertEqual(data["quiz"][0]["id"], "stable-question-id")
        self.assertNotIn("Private lesson content", self.gate)
        self.assertIn("(()=>{\nconst DATA=", self.gate)
        self.assertIn("const SKEY='lumora-english-pass'", self.gate)
        self.assertNotIn("getItem('lumora-pass')", self.gate)

    def test_missing_and_wrong_password_fail_closed(self):
        with self.assertRaises(ValueError):
            verify(self.gate, "")
        with self.assertRaises(InvalidTag):
            verify(self.gate, "incorrect")

    def test_runtime_upgrade_preserves_authenticated_ciphertext_and_private_content(self):
        blob, template = envelope(self.gate)
        legacy = english_gate(template, runtime=False)
        refreshed = refresh_runtime(legacy)
        self.assertEqual(envelope(refreshed)[0], blob)
        self.assertEqual(verify(refreshed, "temporary-test-password"), verify(legacy, "temporary-test-password"))
        self.assertNotIn("Private lesson content", refreshed)
        integrity = base64.b64encode(hashlib.sha384(RUNTIME.read_bytes()).digest()).decode()
        self.assertIn("sha384-" + integrity, refreshed)
        self.assertIn("document.write(prepareEnglish(html))", refreshed)
        with self.assertRaises(InvalidTag):
            verify(refreshed, "incorrect")

    def test_next_runtime_update_can_refresh_the_previous_signed_shell(self):
        previous_blob = envelope(self.gate)[0]
        with mock.patch('english_release.RUNTIME') as runtime:
            runtime.read_bytes.return_value = b'/* next reviewed game build */'
            refreshed = refresh_runtime(self.gate)
            self.assertNotEqual(refreshed, self.gate)
            self.assertEqual(envelope(refreshed)[0], previous_blob)
            self.assertEqual(verify(refreshed, "temporary-test-password")["quiz"][0]["id"], "stable-question-id")
            self.assertEqual(refresh_runtime(refreshed), refreshed)

    def test_plaintext_or_appended_content_is_rejected(self):
        for invalid in (self.source, self.gate + self.source):
            with self.assertRaises(ValueError):
                verify(invalid, "temporary-test-password")

    def test_rebuild_restores_subdirectory_and_failed_validation_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            release, output = Path(tmp) / "encrypted.html", Path(tmp) / "docs/english/index.html"
            release.write_text(self.gate)
            install(release, output, "temporary-test-password")
            self.assertEqual(output.read_text(), self.gate)
            self.assertEqual((output.parent / "game-runtime.js").read_bytes(), RUNTIME.read_bytes())
            output.unlink()
            install(release, output, "temporary-test-password")
            with self.assertRaises(InvalidTag):
                install(release, output, "incorrect")
            self.assertEqual(output.read_text(), self.gate)


if __name__ == "__main__":
    unittest.main()
