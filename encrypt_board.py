#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把看板 HTML 加密成"输密码才解密"的自包含页面。
真加密:PBKDF2-HMAC-SHA256 派生密钥 + AES-256-GCM;浏览器端用 WebCrypto 解密。
密码从环境变量 BOARD_PASSWORD 读;未设则原样输出(不加密),即可选开关。
用法:python3 encrypt_board.py <输入html> <输出html>"""
import sys, os, json, base64, hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERS = 250000

def encrypt(html: str, password: str) -> str:
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERS, 32)
    ct = AESGCM(key).encrypt(iv, html.encode("utf-8"), None)   # 密文含 16 字节 GCM tag
    b64 = lambda b: base64.b64encode(b).decode()
    blob = json.dumps({"s": b64(salt), "i": b64(iv), "c": b64(ct), "n": ITERS})
    return GATE.replace("/*__BLOB__*/", blob)

# 解密门页:输密码 → WebCrypto 解密 → document.write 还原整张看板
GATE = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<title>同光科技 · 需要访问密码</title>
<meta name="robots" content="noindex,nofollow">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC",sans-serif;background:#0b1120;color:#e2e8f0;
min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid #334155;border-radius:16px;
padding:34px 30px;max-width:360px;width:100%;text-align:center}
.ic{font-size:34px;margin-bottom:10px}
h1{font-size:19px;font-weight:800;color:#60a5fa;margin-bottom:6px}
p{font-size:13px;color:#94a3b8;margin-bottom:20px}
input{width:100%;padding:12px 14px;font-size:16px;border-radius:10px;border:1px solid #334155;
background:#0b1120;color:#e2e8f0;outline:none;text-align:center;letter-spacing:2px}
input:focus{border-color:#60a5fa}
button{width:100%;margin-top:12px;padding:12px;font-size:15px;font-weight:700;border:none;border-radius:10px;
background:#2563eb;color:#fff;cursor:pointer}
button:active{background:#1d4ed8}
.err{color:#f87171;font-size:12.5px;margin-top:10px;min-height:16px}
.hint{color:#475569;font-size:11px;margin-top:16px}
</style></head><body>
<div class="box">
 <div class="ic">🔒</div>
 <h1>美股 AI 科技股早报</h1>
 <p>此看板受密码保护,请输入访问密码</p>
 <form id="f"><input id="pw" type="password" inputmode="numeric" placeholder="密码" autofocus autocomplete="off"/>
 <button type="submit">进入看板</button></form>
 <div class="err" id="err"></div>
 <div class="hint">仅研究示范 · 非投资建议</div>
</div>
<script>
const DATA=/*__BLOB__*/;
const b2a=b=>Uint8Array.from(atob(b),c=>c.charCodeAt(0));
document.getElementById('f').addEventListener('submit',async e=>{
  e.preventDefault();
  const err=document.getElementById('err'); err.textContent='解密中…';
  const pw=document.getElementById('pw').value;
  try{
    const enc=new TextEncoder();
    const km=await crypto.subtle.importKey('raw',enc.encode(pw),'PBKDF2',false,['deriveKey']);
    const key=await crypto.subtle.deriveKey(
      {name:'PBKDF2',salt:b2a(DATA.s),iterations:DATA.n,hash:'SHA-256'},
      km,{name:'AES-GCM',length:256},false,['decrypt']);
    const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b2a(DATA.i)},key,b2a(DATA.c));
    const html=new TextDecoder().decode(pt);
    document.open();document.write(html);document.close();
  }catch(ex){ err.textContent='密码错误'; }
});
</script></body></html>"""

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    pw = (os.environ.get("BOARD_PASSWORD") or "").strip()
    html = open(src, encoding="utf-8").read()
    if not pw:
        open(dst, "w", encoding="utf-8").write(html)
        print(f"ℹ️ 未设 BOARD_PASSWORD,{dst} 未加密(公开)")
    else:
        open(dst, "w", encoding="utf-8").write(encrypt(html, pw))
        print(f"🔒 已加密 {dst}(密码保护)")
