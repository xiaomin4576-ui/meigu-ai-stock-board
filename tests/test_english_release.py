import json
import hashlib
import base64
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cryptography.exceptions import InvalidTag
from english_release import install, package, verify, envelope, refresh_runtime, english_gate, RUNTIME, AUDIO, decrypt_course_transport
from encrypt_board import ITERS
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


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

    def test_operator_encrypted_content_is_repacked_privately_without_exporting_credentials(self):
        password = 'temporary-test-password'
        credential = hashlib.sha256(('andy-english-speech-v1\0' + password).encode()).hexdigest()
        site_hash = hashlib.sha256(credential.encode()).hexdigest()
        salt, iv = b's' * 16, b'i' * 12
        key = hashlib.pbkdf2_hmac('sha256', ('andy-english-course-build-v1\0' + site_hash).encode(), salt, ITERS, 32)
        cipher = AESGCM(key).encrypt(iv, self.source.encode(), None)
        blob = {'version': 1, 'keyScheme': 'site-login-build-v1',
                's': base64.b64encode(salt).decode(), 'i': base64.b64encode(iv).decode(),
                'c': base64.b64encode(cipher).decode(), 'n': ITERS}
        self.assertEqual(decrypt_course_transport(blob, password), self.source)
        with self.assertRaises(InvalidTag):
            decrypt_course_transport(blob, 'incorrect')
        for patch in [{'n': 1}, {'keyScheme': 'other'}, {'version': 2}, {'i': ''}]:
            with self.assertRaises(ValueError):
                decrypt_course_transport({**blob, **patch}, password)
        with tempfile.TemporaryDirectory() as tmp:
            release, transport, output = [Path(tmp) / x for x in ('encrypted.html','course-update.enc.json','site/index.html')]
            release.write_text(self.gate)
            transport.write_text(json.dumps(blob))
            install(release, output, password, transport=transport)
            self.assertEqual(verify(output.read_text(), password)['quiz'][0]['id'], 'stable-question-id')
            receipt = json.loads((output.parent / 'release.json').read_text())
            self.assertEqual(receipt['pageSha256'], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertNotIn(password, output.read_text())
            self.assertNotIn(site_hash, transport.read_text())

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
            self.assertEqual((output.parent / "audio/bedroom-human-us.mp3").read_bytes(), (AUDIO / 'bedroom-human-us.mp3').read_bytes())
            self.assertIn('CC BY-SA 3.0', (output.parent / 'audio/ATTRIBUTION.md').read_text())
            output.unlink()
            install(release, output, "temporary-test-password")
            with self.assertRaises(InvalidTag):
                install(release, output, "incorrect")
            self.assertEqual(output.read_text(), self.gate)


if __name__ == "__main__":
    unittest.main()
