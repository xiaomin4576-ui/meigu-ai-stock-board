#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把看板 HTML 加密成"输密码才解密"的自包含页面。
真加密:PBKDF2-HMAC-SHA256 派生密钥 + AES-256-GCM;浏览器端用 WebCrypto 解密。
密码从环境变量 BOARD_PASSWORD 读;未设则原样输出(不加密),即可选开关。
用法:python3 encrypt_board.py <输入html> <输出html>"""
import sys, os, json, base64, hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERS = 250000

def section_of(path: str) -> str:
    """按输出文件名给密码门标注正确板块名——此前所有门都写死「美股 AI 科技股早报」,
    访客在头条/运营页门口看到股票标题会困惑(体检发现)。"""
    b = os.path.basename(path)
    if b == "news.html":
        return "全球市场头条"
    if b == "ops.html":
        return "运营看板"
    if b == "africa.html":
        return "非洲科技脉搏"
    if b == "archive.html":
        return "看板归档"
    if b.startswith("ai_stock_board_") or b == "board.html":
        return "AI 股票看板"
    if b == "home.html":
        return "LUMORA · 同光科技"          # 门户首页(四板块入口),经光之门进入
    return "LUMORA · 同光科技"


def encrypt(html: str, password: str, section: str = "AI 股票看板") -> str:
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERS, 32)
    ct = AESGCM(key).encrypt(iv, html.encode("utf-8"), None)   # 密文含 16 字节 GCM tag
    b64 = lambda b: base64.b64encode(b).decode()
    blob = json.dumps({"s": b64(salt), "i": b64(iv), "c": b64(ct), "n": ITERS})
    return GATE.replace("/*__BLOB__*/", blob).replace("__SECTION__", section)

# 解密门页:输密码 → WebCrypto 解密 → document.write 还原整张看板
GATE = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<title>同光科技 · 需要访问密码</title>
<meta name="robots" content="noindex,nofollow">
<script>/* 防闪:已通行(sessionStorage有pass)则首帧就隐藏密码框、显"解锁中",绝不闪现密码环节 */
try{if(sessionStorage.getItem('lumora-pass'))document.documentElement.className='unlocking';}catch(e){}</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC",sans-serif;background:#0a1020;color:#f2f6fc;
min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{background:linear-gradient(135deg,#1c2a4a,#101b33);border:1px solid #2f4166;border-radius:16px;
padding:34px 30px;max-width:360px;width:100%;text-align:center}
.ic{font-size:34px;margin-bottom:10px}
h1{font-size:19px;font-weight:800;color:#7ab8ff;margin-bottom:6px}
p{font-size:14px;color:#94a6c4;margin-bottom:20px}
input{width:100%;padding:12px 14px;font-size:16px;border-radius:10px;border:1px solid #2f4166;
background:#0a1020;color:#f2f6fc;outline:none;text-align:center;letter-spacing:2px}
input:focus{border-color:#7ab8ff}
button{width:100%;margin-top:12px;padding:12px;font-size:15px;font-weight:700;border:none;border-radius:10px;
background:#2563eb;color:#fff;cursor:pointer}
button:active{background:#1d4ed8}
.err{color:#ff8080;font-size:14px;margin-top:10px;min-height:16px}
.hint{color:#94a6c4;font-size:12px;margin-top:16px}
/* 防闪:unlocking 态隐藏密码框、显解锁 spinner(已通行时首帧即生效) */
.unlocking .box{display:none}
#loader{display:none;position:fixed;inset:0;flex-direction:column;align-items:center;justify-content:center;gap:14px;color:#94a6c4;font-size:14px;letter-spacing:1px}
.unlocking #loader{display:flex}
#loader .sp{width:28px;height:28px;border:2px solid rgba(226,192,126,.22);border-top-color:#e2c07e;border-radius:50%;animation:ldsp .7s linear infinite}
@keyframes ldsp{to{transform:rotate(360deg)}}
</style></head><body>
<div id="loader"><div class="sp"></div>解锁中…</div>
<div class="box">
 <div class="ic">🔒</div>
 <h1>__SECTION__</h1>
 <p>LUMORA · 同光科技 · 此页受密码保护,请输入访问密码</p>
 <form id="f"><input id="pw" type="password" inputmode="numeric" placeholder="密码" autofocus autocomplete="off"/>
 <button type="submit">进入看板</button></form>
 <div class="err" id="err"></div>
 <div class="hint">仅研究示范 · 非投资建议</div>
</div>
<script>
const DATA=/*__BLOB__*/;
const b2a=b=>Uint8Array.from(atob(b),c=>c.charCodeAt(0));
async function tryDecrypt(pw){
  const enc=new TextEncoder();
  const km=await crypto.subtle.importKey('raw',enc.encode(pw),'PBKDF2',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey(
    {name:'PBKDF2',salt:b2a(DATA.s),iterations:DATA.n,hash:'SHA-256'},
    km,{name:'AES-GCM',length:256},false,['decrypt']);
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b2a(DATA.i)},key,b2a(DATA.c));
  return new TextDecoder().decode(pt);
}
// 全站通行:光之门主页输一次密码存 sessionStorage,各加密页自动解——不再每页各输一遍
(async function(){
  const saved=sessionStorage.getItem('lumora-pass');
  if(!saved)return;
  try{
    const html=await tryDecrypt(saved);
    document.open();document.write(html);document.close();
  }catch(ex){ sessionStorage.removeItem('lumora-pass'); document.documentElement.classList.remove('unlocking'); }
})();
document.getElementById('f').addEventListener('submit',async e=>{
  e.preventDefault();
  const err=document.getElementById('err'); err.textContent='解密中…';
  const pw=document.getElementById('pw').value;
  try{
    const html=await tryDecrypt(pw);
    sessionStorage.setItem('lumora-pass',pw);
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
        open(dst, "w", encoding="utf-8").write(encrypt(html, pw, section_of(dst)))
        print(f"🔒 已加密 {dst}(密码保护·门标「{section_of(dst)}」)")
