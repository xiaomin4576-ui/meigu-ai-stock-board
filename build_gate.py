#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""光之门(LUMORA Gate)——站点公开入口页 docs/index.html。

设计意图(同光=光,LUMORA≈luminous):
  · 科技感 + 光元素的品牌闪屏:LUMORA 金属光泽字标 + 地平线金线 + 双光晕 + 星点呼吸。
  · 输入访问密码 → 本地 AES-GCM 校验(密文 blob 内嵌本页)→ 校验通过播放「时光隧道」:
    多束光旋着汇聚成一束 → 绽开满屏白光 → document.write 直出 home 内容(零闪断进站)。
  · 已通行(sessionStorage 有 lumora-pass)则跳过门,直接 location.replace 到 home.html。

工程要点:
  · 本页公开、不加密(它就是密码入口),但 home 明文只以【密文】形式嵌入本页(与 encrypt_board 同格式:PBKDF2-HMAC-SHA256 250000 轮 + AES-256-GCM),
    浏览器端 WebCrypto 解密——密码不对拿不到任何明文,和其它加密页同等安全。
  · 模板用 raw 字符串 + /*__BLOB__*/ 占位(不用 f-string),CSS/JS 花括号无需转义。
  · document.write 会销毁旧文档,故「白光淡出」由注入的新 home 文档自带 #lumflash overlay 完成;
    注入时把 overlay 塞进 <body> 之后、keyframes 塞进 </head> 之前,保持 home 的标准渲染模式(不因前置内容掉进 quirks mode)。
  · 未设 BOARD_PASSWORD(公开模式):index.html 直接落 home 明文(旧公开行为),不生成门。

用法:python3 build_gate.py <home明文html> <输出index.html>
"""
import sys, os, json, base64, hashlib

ITERS = 250000  # 与 encrypt_board.py 保持一致,复用同一套解密逻辑


def make_blob(html: str, password: str) -> str:
    """把 home 明文加密成 {s,i,c,n} JSON(字段名与 encrypt_board 一致,前端 tryDecrypt 通用)。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # 延迟导入:公开模式(无密码)无需 cryptography
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERS, 32)
    ct = AESGCM(key).encrypt(iv, html.encode("utf-8"), None)  # 含 16B GCM tag
    b64 = lambda b: base64.b64encode(b).decode()
    return json.dumps({"s": b64(salt), "i": b64(iv), "c": b64(ct), "n": ITERS})


GATE = r"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">
<title>LUMORA · 同光科技</title>
<meta name="robots" content="noindex,nofollow">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{font-family:-apple-system,"PingFang SC",sans-serif;min-height:100dvh;display:flex;flex-direction:column;
align-items:center;justify-content:center;overflow:hidden;padding:40px 20px;color:#f5f7fb;
background:radial-gradient(ellipse 120% 80% at 50% 28%,#101b36 0%,#0b1120 55%,#070d1a 100%)}
/* —— 氛围光晕(固定层,零交互) —— */
.halo{position:fixed;border-radius:50%;pointer-events:none;z-index:0}
.halo.g{width:600px;height:600px;left:-10%;top:-15%;background:radial-gradient(circle,rgba(200,165,98,.14),transparent 70%);filter:blur(60px);animation:driftG 60s ease-in-out infinite alternate}
.halo.b{width:720px;height:720px;right:-15%;bottom:-20%;background:radial-gradient(circle,rgba(96,165,250,.10),transparent 70%);filter:blur(60px);animation:driftB 60s ease-in-out infinite alternate}
@keyframes driftG{to{transform:translate(40px,30px)}}
@keyframes driftB{to{transform:translate(-40px,-30px)}}
/* —— 星点 canvas(静态,画一次) —— */
#stars{position:fixed;inset:0;z-index:0;pointer-events:none}
.star{position:fixed;width:2px;height:2px;border-radius:50%;background:#eef2f9;box-shadow:0 0 6px 1px rgba(238,242,249,.7);z-index:0;pointer-events:none;animation:twinkle 4s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:.8}}
/* —— 主体 —— */
.stage{position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;width:100%}
.brand{font-family:Georgia,"Times New Roman",serif;font-weight:700;color:#f5f7fb;line-height:1;
font-size:clamp(40px,8vw,64px);letter-spacing:clamp(6px,2vw,16px);text-indent:clamp(6px,2vw,16px);
text-shadow:0 0 32px rgba(200,165,98,.28),0 0 2px rgba(245,247,251,.4);animation:fadeUp .9s ease both}
.sub{margin-top:18px;font-size:14px;letter-spacing:8px;text-indent:8px;color:#e3c37f;animation:fadeUp .9s ease .1s both}
.ray{margin-top:26px;width:min(480px,72vw);height:1px;transform:scaleX(0);transform-origin:center;
background:linear-gradient(90deg,transparent,rgba(200,165,98,.9),transparent);
box-shadow:0 0 24px 2px rgba(200,165,98,.35);animation:rayIn .9s cubic-bezier(.22,1,.36,1) .3s forwards}
.slogan{margin-top:22px;font-size:13px;color:#9db1c9;letter-spacing:1px;animation:fadeUp .9s ease .4s both}
/* —— 密码输入区 —— */
.gate{margin-top:56px;width:min(360px,86vw);position:relative;animation:fadeUp .9s ease .5s both}
#pw{width:100%;height:52px;font-size:16px;color:#eef2f9;letter-spacing:4px;font-family:inherit;
background:rgba(11,17,32,.6);border:1px solid rgba(157,177,201,.28);border-radius:12px;
padding:0 62px 0 18px;outline:none;transition:border-color .25s,box-shadow .25s}
#pw::placeholder{color:#8296ad;letter-spacing:2px}
#pw:focus{border-color:#c8a562;box-shadow:0 0 0 3px rgba(200,165,98,.18),0 0 24px rgba(200,165,98,.22)}
#pw.err{border-color:#ff8f8f;animation:shake .26s}
@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-6px)}40%{transform:translateX(6px)}60%{transform:translateX(-4px)}80%{transform:translateX(4px)}}
#go{position:absolute;right:6px;top:6px;width:44px;height:44px;border:none;border-radius:9px;cursor:pointer;
background:linear-gradient(135deg,#e3c37f,#c8a562);display:flex;align-items:center;justify-content:center;transition:filter .2s,transform .1s}
#go:hover{filter:brightness(1.08)}#go:active{transform:scale(.96)}#go:disabled{cursor:default}
#go svg{display:block}
.spin{width:18px;height:18px;border:2px solid rgba(11,17,32,.25);border-top-color:#0b1120;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.msg{min-height:16px;margin-top:12px;font-size:12px;color:#ff8f8f;text-align:center;letter-spacing:.5px}
.foot{margin-top:auto;padding-top:40px;padding-bottom:8px;font-size:12px;color:#8296ad;text-align:center;letter-spacing:.5px;z-index:2}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes rayIn{to{transform:scaleX(1)}}
/* —— 隧道 canvas(成功后显现) —— */
#tunnel{position:fixed;inset:0;z-index:9998;display:none;background:transparent}
/* —— 移动端克制 —— */
@media(max-width:640px){
  .brand{letter-spacing:6px;text-indent:6px}
  .halo{opacity:.5;animation:none}
  .halo.g{opacity:.5}.halo.b{opacity:.5}
  .ray{width:82vw}
}
@media(prefers-reduced-motion:reduce){
  .halo{animation:none}
  .brand,.sub,.ray,.slogan,.gate{animation:none;transform:none;opacity:1}
  .ray{transform:scaleX(1)}
}
</style></head><body>
<div class="halo g"></div><div class="halo b"></div>
<canvas id="stars"></canvas>
<span class="star" style="left:18%;top:22%;animation-duration:4.5s"></span>
<span class="star" style="left:82%;top:30%;animation-duration:5.5s;animation-delay:.6s"></span>
<span class="star" style="left:30%;top:70%;animation-duration:3.5s;animation-delay:1.2s"></span>
<span class="star" style="left:70%;top:78%;animation-duration:6s;animation-delay:.3s"></span>
<span class="star" style="left:50%;top:14%;animation-duration:4s;animation-delay:1.8s"></span>
<span class="star" style="left:88%;top:60%;animation-duration:5s;animation-delay:.9s"></span>
<div class="stage">
  <div class="brand">LUMORA</div>
  <div class="sub">同 光 科 技</div>
  <div class="ray"></div>
  <div class="slogan">企业 AI 情报 · 全球市场头条 · AI 产业链股票研判</div>
  <form class="gate" id="f" autocomplete="off">
    <input id="pw" type="password" inputmode="numeric" placeholder="输入访问密码" autofocus autocomplete="off"/>
    <button id="go" type="submit" aria-label="进入">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0b1120" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg>
    </button>
  </form>
  <div class="msg" id="msg"></div>
</div>
<div class="foot">LUMORA · 同光科技 · andy4576.com · 仅供研究学习,非投资建议</div>
<canvas id="tunnel"></canvas>
<script>
// —— 已通行则跳过门(乐观跳转;密文页会用同一密码自动解密)——
// try/catch 必须:沙箱 iframe / 禁用存储 / 隐私模式下裸访问 sessionStorage 会抛 SecurityError,
// 若不捕获会中止整段内联脚本→下方 submit 监听器挂不上→门彻底失效。存储不可用时当作未通行,照常渲染门。
(function(){ try{ if(sessionStorage.getItem('lumora-pass')){ location.replace('home.html'); } }catch(e){} })();

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

// —— 静态星点(画一次)——
(function(){
  try{
    const cv=document.getElementById('stars');const dpr=Math.min(devicePixelRatio||1,2);
    const w=innerWidth,h=innerHeight;cv.width=w*dpr;cv.height=h*dpr;cv.style.width=w+'px';cv.style.height=h+'px';
    const g=cv.getContext('2d');g.scale(dpr,dpr);
    for(let i=0;i<60;i++){const r=0.5+Math.random()*0.7,a=0.15+Math.random()*0.45;
      g.beginPath();g.arc(Math.random()*w,Math.random()*h,r,0,6.283);g.fillStyle='rgba(238,242,249,'+a+')';g.fill();}
  }catch(e){}
})();

// —— 注入 home 明文(保持标准渲染模式 + 自带白幕淡出)——
function injectHome(html){
  // 白幕 overlay:CSS 动画平滑淡出;再挂 700ms setTimeout 强制移除做兜底——
  // 万一某浏览器动画未生效,也绝不把整屏白幕永久盖在 home 上(可怕失败模式)。
  const FLASH='<div id="lumflash" style="position:fixed;inset:0;background:#fff;z-index:99999;pointer-events:none;animation:lumfade .45s ease .05s forwards"></div>'
    +'<script>setTimeout(function(){var e=document.getElementById("lumflash");if(e&&e.parentNode)e.parentNode.removeChild(e);},700)<\/script>';
  const KEY='<style>@keyframes lumfade{to{opacity:0;visibility:hidden}}</style>';
  let out=html;
  if(out.indexOf('</head>')>-1 && /<body[^>]*>/.test(out)){
    out=out.replace('</head>',KEY+'</head>').replace(/<body([^>]*)>/,'<body$1>'+FLASH);
  }else{
    out=KEY+FLASH+out; // 兜底:结构异常也不阻断进站
  }
  document.open();document.write(out);document.close();
}

// —— 时光隧道(canvas 2D,1900ms 四阶段;时间驱动,掉帧不拖慢)——
function playTunnel(html){
  const reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;
  const cv=document.getElementById('tunnel');
  let ctx=null; try{ctx=cv.getContext('2d');}catch(e){}
  let done=false;
  const inject=()=>{ if(done)return; done=true; injectHome(html); };
  setTimeout(inject,2400); // 兜底:rAF 被后台节流也保证进站

  if(reduce||!ctx){ // 降级:一层白幕淡入后直出
    cv.style.display='block';cv.style.background='#fff';cv.style.transition='opacity 0s';cv.style.opacity='0';
    requestAnimationFrame(()=>{cv.style.transition='opacity .3s ease';cv.style.opacity='1';});
    setTimeout(inject,340); return;
  }

  const mobile=innerWidth<640||matchMedia('(pointer:coarse)').matches;
  const dpr=Math.min(devicePixelRatio||1,mobile?1.5:2);
  const w=innerWidth,h=innerHeight;
  cv.style.display='block';cv.width=w*dpr;cv.height=h*dpr;
  ctx.scale(dpr,dpr);
  const cx=w/2,cy=h/2,maxR=Math.sqrt(w*w+h*h)/2,diag=maxR*2;
  const N=mobile?120:220,TAU=Math.PI*2;
  const COLS=[]; for(let i=0;i<N;i++){const q=Math.random();
    COLS.push(q<0.6?'200,165,98':(q<0.9?'125,184,255':'238,242,249'));}
  const P=new Array(N);
  for(let i=0;i<N;i++){const a=Math.random()*TAU;
    P[i]={a:a,r0:maxR*(0.75+Math.random()*0.5),swirl:(Math.random()-0.5)*1.2,
      col:COLS[i],alpha:0.5+Math.random()*0.4,px:cx+Math.cos(a)*maxR,py:cy+Math.sin(a)*maxR};}
  const easeInCubic=p=>p*p*p, easeOutCubic=p=>1-Math.pow(1-p,3), easeOutQuart=p=>1-Math.pow(1-p,4);
  const t0=performance.now();
  function frame(now){
    const t=now-t0;
    // 拖尾:整屏半透明填充制造运动模糊(远比逐粒子存轨迹便宜)
    ctx.globalCompositeOperation='source-over';
    ctx.fillStyle='rgba(7,13,26,.22)';ctx.fillRect(0,0,w,h);
    ctx.globalCompositeOperation='lighter';
    // 阶段 A+B:粒子旋着汇聚
    if(t<1300){
      const p=easeInCubic(Math.min(t/900,1));
      for(let i=0;i<N;i++){const pt=P[i];
        const shrink=t<900?1:Math.max(0,1-(t-900)/250);
        const r=pt.r0*(1-p)*shrink;
        const a=pt.a+pt.swirl*(1-p);
        const x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r;
        if(r>2){ctx.beginPath();ctx.moveTo(pt.px,pt.py);ctx.lineTo(x,y);
          ctx.strokeStyle='rgba('+pt.col+','+pt.alpha+')';
          ctx.lineWidth=1+1.5*(1-r/maxR);ctx.stroke();}
        pt.px=x;pt.py=y;}
    }
    // 阶段 B:合成一束水平光(金/蓝/白三层)
    if(t>900&&t<1400){
      const q=easeOutCubic(Math.min((t-900)/400,1)),half=q*w/2;
      const beam=(lw,c)=>{ctx.beginPath();ctx.moveTo(cx-half,cy);ctx.lineTo(cx+half,cy);
        ctx.strokeStyle=c;ctx.lineWidth=lw;ctx.lineCap='round';ctx.stroke();};
      beam(5,'rgba(200,165,98,.5)');beam(3,'rgba(125,184,255,.6)');beam(1.5,'rgba(255,255,255,.95)');
    }
    // 中心光核
    const R=14*Math.min(t/900,1)+(t>900?14*Math.min((t-900)/400,1):0);
    if(R>0){const grd=ctx.createRadialGradient(cx,cy,0,cx,cy,R);
      grd.addColorStop(0,'rgba(255,255,255,.95)');grd.addColorStop(.5,'rgba(226,192,126,.7)');grd.addColorStop(1,'rgba(226,192,126,0)');
      ctx.fillStyle=grd;ctx.beginPath();ctx.arc(cx,cy,R,0,TAU);ctx.fill();}
    // 阶段 C:绽开满屏白
    if(t>1300){
      const q=easeOutQuart(Math.min((t-1300)/350,1));
      const rad=30+q*diag;
      const wg=ctx.createRadialGradient(cx,cy,0,cx,cy,rad);
      wg.addColorStop(0,'rgba(255,255,255,1)');wg.addColorStop(1,'rgba(255,255,255,0)');
      ctx.fillStyle=wg;ctx.beginPath();ctx.arc(cx,cy,rad,0,TAU);ctx.fill();
      ctx.globalCompositeOperation='source-over';
      ctx.fillStyle='rgba(255,255,255,'+(q*0.95)+')';ctx.fillRect(0,0,w,h);
      if(q>=0.9){inject();return;}
    }
    if(!done) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// —— 表单提交 ——
const pw=document.getElementById('pw'),msg=document.getElementById('msg'),go=document.getElementById('go'),f=document.getElementById('f');
const ARROW=go.innerHTML;
f.addEventListener('submit',async e=>{
  e.preventDefault();
  const val=pw.value; if(!val)return;
  msg.textContent='';go.disabled=true;go.innerHTML='<span class="spin"></span>';
  try{
    const html=await tryDecrypt(val);
    try{ sessionStorage.setItem('lumora-pass',val); }catch(e){}  // 存储不可用不应阻断进站(否则正确密码误入 catch 显“密码不对”)
    playTunnel(html);
  }catch(ex){
    go.disabled=false;go.innerHTML=ARROW;
    pw.classList.add('err');msg.textContent='密码不对,再试一次';
    setTimeout(()=>{pw.classList.remove('err');},800);
    pw.select();
  }
});
</script></body></html>"""


def build(home_html: str, password: str) -> str:
    blob = make_blob(home_html, password)
    return GATE.replace("/*__BLOB__*/", blob)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    pw = (os.environ.get("BOARD_PASSWORD") or "").strip()
    home = open(src, encoding="utf-8").read()
    if not pw:
        # 公开模式:无密码,index 直接落 home 明文(旧公开行为,不生成门)
        open(dst, "w", encoding="utf-8").write(home)
        print(f"ℹ️ 未设 BOARD_PASSWORD,{dst} 落 home 明文(公开,无光之门)")
    else:
        open(dst, "w", encoding="utf-8").write(build(home, pw))
        print(f"✨ 光之门已生成 {dst}(内嵌 home 密文 blob,密码校验+时光隧道)")
