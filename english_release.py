#!/usr/bin/env python3
"""Package a private English build, or verify/copy its encrypted release to Pages."""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request
import urllib.error
import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from encrypt_board import GATE, ITERS, encrypt

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / "english" / "encrypted.html"
RUNTIME = ROOT / "english" / "game-runtime.js"


def english_gate(gate, runtime=True):
    # Keep gate variables out of the restored application's global lexical scope.
    gate = (gate.replace("<script>\nconst DATA=", "<script>\n(()=>{\nconst DATA=")
            .replace("</script></body></html>", "})();\n</script></body></html>")
            .replace("进入看板", "进入英语学习")
            .replace("此页受密码保护,请输入访问密码", "请输入英语版块的独立访问密码")
            .replace("仅研究示范 · 非投资建议", "Andy 英语日课 · 持续学习与复习")
            .replace("  /* 普通页 lumora-pass(通行8888);运营看板 lumora-admin(独立管理员密码,不共享) */", ""))
    if runtime:
        code = RUNTIME.read_bytes()
        version = hashlib.sha256(code).hexdigest()[:16]
        integrity = base64.b64encode(hashlib.sha384(code).digest()).decode()
        tag = (f'<script src="/english/game-runtime.js?v={version}" '
               f'integrity="sha384-{integrity}" crossorigin="anonymous"></script>')
        quoted_tag = json.dumps(tag).replace("</", "<\\/")
        loader = ("function prepareEnglish(html){\n"
                  "  const game=/<script>\\s*\\/\\* Continuous voice practice\\.[\\s\\S]*?<\\/script>/;\n"
                  f"  return html.replace(game,()=>{quoted_tag});\n"
                  "}\n")
        gate = gate.replace("const b2a=b=>", loader + "const b2a=b=>")
        gate = gate.replace("document.write(html)", "document.write(prepareEnglish(html))")
    return gate


def envelope(gate):
    match = re.search(r'const DATA=(\{[^\n]+\});', gate)
    if not match:
        raise ValueError("English release must be an encrypted gate")
    blob = json.loads(match[1])
    template = (GATE.replace("/*__BLOB__*/", match[1])
                .replace("__SECTION__", "英语学习")
                .replace("__SKEY__", "lumora-english-pass"))
    if (gate not in (english_gate(template), english_gate(template, runtime=False))
            or set(blob) != {"s", "i", "c", "n"} or blob["n"] != ITERS):
        raise ValueError("Unexpected English gate format")
    return blob, template


def refresh_runtime(gate):
    # Update only the public application shell; private course ciphertext is unchanged.
    _, template = envelope(gate)
    return english_gate(template)


def course_data(html):
    match = re.search(r'<script id="course-data" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("Missing course data in English build")
    data = json.loads(match[1])
    if not data.get("units") or not data.get("quiz"):
        raise ValueError("English build has no lessons or questions")
    if 'href="/"' not in html:
        raise ValueError("English build is missing the main-site return link")
    return data


def package(html, password):
    if not password:
        raise ValueError("A password is required; plaintext releases are not allowed")
    course_data(html)
    return english_gate(encrypt(html, password, "英语学习", "lumora-english-pass"))


def verify(gate, password):
    if not password:
        raise ValueError("ENGLISH_PASSWORD is required to install English")
    blob, _ = envelope(gate)
    salt, iv, cipher = [base64.b64decode(blob[k], validate=True) for k in ("s", "i", "c")]
    if len(salt) != 16 or len(iv) != 12:
        raise ValueError("Invalid encryption parameters")
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERS, 32)
    # Authentication failure stops deployment; decrypted content stays in memory.
    html = AESGCM(key).decrypt(iv, cipher, None).decode()
    return course_data(html)


def install(release, output, password):
    gate = release.read_text(encoding="utf-8")
    data = verify(gate, password)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(gate, encoding="utf-8")
    (output.parent / "game-runtime.js").write_bytes(RUNTIME.read_bytes())
    return data


def check_speech_login(password):
    if not password:
        raise ValueError("ENGLISH_PASSWORD is required for connection verification")
    # The same credential derivation used by the browser; never print it or upload audio.
    credential = hashlib.sha256(('andy-english-speech-v1\0' + password).encode()).hexdigest()
    request = urllib.request.Request(
        'https://speech.andy4576.com/session',
        data=json.dumps({'password': credential}).encode(),
        headers={'Content-Type': 'application/json', 'Origin': 'https://andy4576.com'},
        method='POST',
    )
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=10) as response:
            session = json.load(response)
        if not re.fullmatch(r'[a-f0-9]{64}', session.get('token', '')):
            raise ValueError("Invalid connection response")
        expires = datetime.datetime.fromisoformat(session.get('expiresAt', '').replace('Z', '+00:00'))
        if expires <= datetime.datetime.now(datetime.timezone.utc):
            raise ValueError("Connection is expired")
    except Exception:
        raise ValueError("Website-to-speech connection verification failed; no audio was uploaded") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack")
    pack.add_argument("source", type=Path)
    pack.add_argument("--output", type=Path, default=RELEASE)
    deploy = commands.add_parser("install")
    deploy.add_argument("--release", type=Path, default=RELEASE)
    deploy.add_argument("--output", type=Path, default=ROOT / "docs/english/index.html")
    refresh = commands.add_parser("refresh-runtime", help="Update public game code without changing encrypted course data")
    refresh.add_argument("--release", type=Path, default=RELEASE)
    commands.add_parser("check-speech-login", help="Verify website scoring connection without uploading audio")
    args = parser.parse_args()
    if args.command == "refresh-runtime":
        gate = args.release.read_text(encoding="utf-8")
        args.release.write_text(refresh_runtime(gate), encoding="utf-8")
        print("English game shell updated; private ciphertext and password gate preserved")
        return
    password = os.environ.get("ENGLISH_PASSWORD", "")
    if args.command == "check-speech-login":
        verify(RELEASE.read_text(encoding="utf-8"), password)
        check_speech_login(password)
        print("Website scoring connection verified; no password, token or audio exported")
        return
    if args.command == "pack":
        if args.source.resolve().is_relative_to(ROOT):
            parser.error("Keep the plaintext English source outside this public repository")
        password = password or getpass.getpass("English section password: ")
        gate = package(args.source.read_text(encoding="utf-8"), password)
        data = verify(gate, password)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(gate, encoding="utf-8")
    else:
        data = install(args.release, args.output, password)
    print(f"English encrypted release verified: {len(data['units'])} units, {len(data['quiz'])} questions")


if __name__ == "__main__":
    main()
