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

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from encrypt_board import GATE, ITERS, encrypt

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / "english" / "encrypted.html"


def english_gate(gate):
    # Keep gate variables out of the restored application's global lexical scope.
    return (gate.replace("<script>\nconst DATA=", "<script>\n(()=>{\nconst DATA=")
            .replace("</script></body></html>", "})();\n</script></body></html>")
            .replace("进入看板", "进入英语学习")
            .replace("仅研究示范 · 非投资建议", "Andy 英语日课 · 持续学习与复习")
            .replace("  /* 普通页 lumora-pass(通行8888);运营看板 lumora-admin(独立管理员密码,不共享) */", ""))


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
    return english_gate(encrypt(html, password, "英语学习", "lumora-pass"))


def verify(gate, password):
    if not password:
        raise ValueError("BOARD_PASSWORD is required to install English")
    match = re.search(r'const DATA=(\{[^\n]+\});', gate)
    if not match:
        raise ValueError("English release must be an encrypted gate")
    blob = json.loads(match[1])
    expected = english_gate(GATE.replace("/*__BLOB__*/", match[1])
                            .replace("__SECTION__", "英语学习")
                            .replace("__SKEY__", "lumora-pass"))
    if gate != expected or set(blob) != {"s", "i", "c", "n"} or blob["n"] != ITERS:
        raise ValueError("Unexpected English gate format")
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
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack")
    pack.add_argument("source", type=Path)
    pack.add_argument("--output", type=Path, default=RELEASE)
    deploy = commands.add_parser("install")
    deploy.add_argument("--release", type=Path, default=RELEASE)
    deploy.add_argument("--output", type=Path, default=ROOT / "docs/english/index.html")
    args = parser.parse_args()
    password = os.environ.get("BOARD_PASSWORD", "")
    if args.command == "pack":
        if args.source.resolve().is_relative_to(ROOT):
            parser.error("Keep the plaintext English source outside this public repository")
        password = password or getpass.getpass("Existing site access password: ")
        gate = package(args.source.read_text(encoding="utf-8"), password)
        data = verify(gate, password)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(gate, encoding="utf-8")
    else:
        data = install(args.release, args.output, password)
    print(f"English encrypted release verified: {len(data['units'])} units, {len(data['quiz'])} questions")


if __name__ == "__main__":
    main()
