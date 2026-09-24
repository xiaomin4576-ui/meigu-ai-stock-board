import json
from pathlib import Path
import tempfile
import unittest

from cryptography.exceptions import InvalidTag
from english_release import install, package, verify


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

    def test_missing_and_wrong_password_fail_closed(self):
        with self.assertRaises(ValueError):
            verify(self.gate, "")
        with self.assertRaises(InvalidTag):
            verify(self.gate, "incorrect")

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
            output.unlink()
            install(release, output, "temporary-test-password")
            with self.assertRaises(InvalidTag):
                install(release, output, "incorrect")
            self.assertEqual(output.read_text(), self.gate)


if __name__ == "__main__":
    unittest.main()
