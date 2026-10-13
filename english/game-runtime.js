/* Continuous voice practice. Only a confirmed gateway pass can score a hit. */
(function(root){
'use strict';
const C=root.EnglishGameCore, STORE='andy-english-game-v1',PREFS='andy-english-game-prefs-v1',ROUND='andy-english-game-round-v1';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let deck=[],groups=[],progress,prefs={learnedGroups:[]},config={},host=null,data,initialized=false,storageOK=true;
let queue=[],index=0,results=[],roundId='',phase='home',status='',mode='all',group='',practice=true,training='warmup';
let hinted=false,translationShown=false,tries=0,requestSerial=0,abort=null,nextTimer=null,blob=null,blobUrl=null,replay=null,token='',expires=0,ready=false,healthChecked=false;
let continuous=false,completedCurrent=false,delayReject=null,speechWait=null;
let recordedText='',lastAssessment=null,replaying=false,replayTimer=null,previousAudioSession=null;
const current=()=>queue[index],busy=()=>continuous||['permission','demo','buffer','recording','encoding','assessing','hit','feedback'].includes(phase);
const canListen=()=>!busy()||['recording','buffer'].includes(phase);
const canReplay=()=>!!blobUrl&&!['permission','encoding','assessing'].includes(phase);
const canUseMic=()=>!busy()||['recording','hit','feedback'].includes(phase);
const recorder=root.EnglishGameAudio.createRecorder();
const cancelled=()=>Object.assign(Error('练习已暂停。'),{code:'CANCELLED'});
const valid=serial=>serial===requestSerial&&!document.hidden&&!!host?.isConnected;
const speech=root.EnglishSpeech.createController({synth:root.speechSynthesis,Utterance:root.SpeechSynthesisUtterance,onChange:s=>{
  if(speechWait&&s.key===speechWait.key){
   if(s.phase==='done'){const wait=speechWait;speechWait=null;wait.resolve();}
   else if(s.phase==='error'||s.phase==='idle'){const wait=speechWait;speechWait=null;wait.reject(Object.assign(Error(s.message||'示范未能播放。'),{code:'DEMO_UNAVAILABLE'}));}
  }
  if(!host?.isConnected)return;
  const line=host.querySelector('#game-speech-status');if(line)line.textContent=s.message||'';
  const b=host.querySelector('[data-game="record"]');if(b&&!busy())b.disabled=['loading','speaking'].includes(s.phase);
}});
function store(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{storageOK=false;}}
function read(key){try{return JSON.parse(localStorage.getItem(key)||'null');}catch{storageOK=false;return null;}}
function save(){store(STORE,progress);}
function init(course){
 if(initialized)return;initialized=true;data=course;deck=C.buildDeck(data);groups=[...new Set(deck.map(x=>x.group))];
 progress=C.sanitizeProgress(null,deck);
 try{const p=read(STORE);if(p)progress=C.sanitizeProgress(p,deck);}catch{storageOK=false;}
 const saved=read(PREFS);if(Array.isArray(saved?.learnedGroups))prefs.learnedGroups=saved.learnedGroups.filter(x=>groups.includes(x));else{prefs.learnedGroups=groups.slice();store(PREFS,prefs);}
 try{config=JSON.parse(document.getElementById('game-config').textContent);}catch{}
 if(config.endpoint){try{const u=new URL(config.endpoint),local=['127.0.0.1','localhost'];if(u.origin!=='https://speech.andy4576.com' && !(u.protocol==='http:'&&local.includes(u.hostname)&&local.includes(location.hostname)))config.endpoint='';else config.endpoint=u.href.replace(/\/$/,'');}catch{config.endpoint='';}}
}
const btn=(action,label,attrs='')=>`<button type="button" data-game="${action}" ${attrs}>${label}</button>`;
const icon=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${name==='mic'?'<rect x="8" y="2" width="8" height="13" rx="4"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>':name==='stop'?'<path d="M8 6v12M16 6v12"/>':'<path d="m9 5 10 7-10 7Z" fill="currentColor" stroke="none"/>'}</svg>`;
// Ship the compact controls with the versioned runtime, including older encrypted course builds.
const controlsStyle=`<style>
.game .game-reading{padding:22px 16px;background:#fff;border-color:var(--game-line)}
.game .game-reading .game-card{padding:12px 8px;border:0;box-shadow:none;background:transparent}
.game .game-reading .game-word{font-size:clamp(2rem,5vw,3rem)}
.game .game-demo-actions{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin:18px 0 0}
.game .game-demo-actions button{min-height:44px;border-radius:24px;padding:8px 18px}
.game .game-voice-controls{display:flex;align-items:center;justify-content:center;gap:32px;margin:20px 0 10px}
.game .game-voice-control{display:flex;flex-direction:column;align-items:center;gap:10px;width:132px;text-align:center;font-size:.88rem;color:var(--game-muted)}
.game .game-voice-controls button{display:grid;place-items:center;flex:none;padding:0;border-radius:50%;box-shadow:none}
.game .game-voice-controls .game-mic{width:96px;height:96px;min-height:96px;background:var(--game-green);border:2px solid var(--game-green);color:#fff}
.game .game-voice-controls .game-mic:not(:disabled):hover{background:var(--game-deep);color:#fff}
.game .game-voice-controls .game-mic.recording{background:#c84054;border-color:#c84054;box-shadow:0 0 0 7px #c840541a}
.game .game-voice-controls .game-mic.recording::before{display:none}
.game .game-voice-controls .game-replay{width:64px;height:64px;min-height:64px;background:#fff;border:1px solid var(--game-line);color:var(--game-green)}
.game .game-voice-controls svg{width:36px;height:36px}
.game .game-voice-controls .game-replay svg{width:27px;height:27px}
.game .game-replay-target{max-width:300px;margin:8px auto;color:var(--game-muted);font-size:.8rem;text-align:center;overflow-wrap:anywhere}
.game .game-score{max-width:460px;margin:16px auto 0;padding:14px 18px;border:1px solid var(--game-line);border-radius:14px;text-align:center;background:#f2f8f3}
.game .game-score.retry{background:#fff3f1;border-color:#e4b1a8;color:#923d32}
.game .game-score.uncertain{background:#fff8e9;border-color:#e6d8b4;color:#79551d}
.game .game-score small{display:block;font-size:.8rem;overflow-wrap:anywhere}
.game .game-score strong{display:block;margin:5px 0;font-size:1.1rem}
.game .game-score .game-score-number{display:block;font-size:1.8rem;font-weight:750;font-variant-numeric:tabular-nums}
.game .game-score-number small{display:inline;margin-left:4px;font-size:.9rem;font-weight:400}
.game .game-score .game-score-detail{margin-top:7px;font-size:.84rem;line-height:1.65}
.game .game-score.previous{padding:10px 12px;background:#fafbf9}
.game .game-score.previous strong{display:inline;font-size:.85rem;margin-right:8px}
.game .game-score.previous .game-score-number{display:inline;font-size:1.1rem}
.game .game-score.previous .game-score-detail{display:none}
.game .game-reading-hint{margin:6px 0;text-align:center;font-size:.86rem;color:var(--game-muted)}
.game .game-skip-row{text-align:center;margin:10px 0}
.game .game-skip-row button{background:transparent;border-color:transparent;text-decoration:underline;text-underline-offset:4px;min-height:44px}
.game .game-reading-notice{margin:16px 0;color:var(--game-muted);font-size:.8rem;line-height:1.6}
.game .game-reading-notice summary{cursor:pointer;min-height:44px;display:flex;align-items:center;justify-content:center}
.game .game-reading-notice p{max-width:540px;margin:0 auto 14px}
.game #game-speech-status:empty,.game #game-feedback:empty{display:none}
.english-recording-player{display:block;width:min(100%,460px);margin:14px auto}
@media(max-width:480px){.game .game-voice-controls{gap:20px}.game .game-reading{padding:16px 10px}.game .game-progress{font-size:.8rem}.game .game-reading .game-card{padding:6px}.game .game-score{padding:12px}.game .game-voice-controls .game-mic{width:88px;height:88px;min-height:88px}}
</style>`;
function scoreView(){
 if(!lastAssessment)return '';
 const {text,outcome,score,feedback}=lastAssessment;
 const previous=!!current()&&text!==current().text;
 const title={pass:'读得清楚',retry:'不太正确，再练会更好',uncertain:'本次未能评分',practice:'已完成跟读 · 未评分'}[outcome];
 return `<div class="game-score ${outcome}${previous?' previous':''}" aria-label="最近一次朗读结果"><small>${previous?'上一词':'刚才读的是'} · <span lang="en">${esc(text)}</span></small><strong>${title}</strong>${score===null?'':`<span class="game-score-number" aria-label="本次评分 ${score}/100">${score}<small>/ 100 分</small></span>`}${feedback?`<div class="game-score-detail">${esc(feedback)}</div>`:''}</div>`;
}
function replayControl(){return `<div class="game-voice-control">${btn('replay',icon(replaying?'stop':'play'),`class="game-replay" aria-label="${replaying?'停止回放':`回放我的录音${recordedText?'：'+esc(recordedText):''}`}" ${canReplay()?'':'disabled'}`)}<span>${replaying?'停止回放':'回放我的录音'}</span></div>`;}
function mascot(){return '<div class="game-hole" aria-hidden="true"><div class="game-mole"><i class="ear left"></i><i class="ear right"></i><div class="face"><i class="eye left"></i><i class="eye right"></i><i class="nose"></i></div><i class="paw left"></i><i class="paw right"></i></div></div>';}
function view(){return '<div id="english-game" class="game"></div>';}
function mount(course,routeGroup){init(course);host=document.getElementById('english-game');
 if(routeGroup){try{const g=decodeURIComponent(routeGroup);if(groups.includes(g)){group=g;mode='group';}}catch{}}
 host.addEventListener('click',handle);host.addEventListener('change',change);
 phase='home';status='';paint();if(config.endpoint&&!healthChecked)checkHealth();
}
async function jsonFetch(path,options={}){
 const response=await fetch(config.endpoint+path,{...options,redirect:'error',cache:'no-store'});
 let result;try{result=await response.json();}catch{throw Error('评分服务暂时没有响应，可以继续跟读练习。');}
 if(!response.ok)throw Object.assign(Error(result.feedback||'评分服务暂时不可用，请稍后重试。'),{status:response.status,code:result.code});return result;
}
async function siteCredential(){
 let password='';try{password=sessionStorage.getItem('lumora-english-pass')||'';}catch{}
 if(!password)throw Error('未读取到英语栏目解锁状态。请返回英语栏目重新输入网站密码，再进入游戏。');
 // Domain-separate the gateway credential: the website password never leaves this page.
 const bytes=new TextEncoder().encode('andy-english-speech-v1\0'+password);
 const digest=await crypto.subtle.digest('SHA-256',bytes);
 return [...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,'0')).join('');
}
async function checkHealth(){
 healthChecked=true;const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),6000);
 try{const h=await jsonFetch('/health',{signal:controller.signal});ready=h.ready===true;}catch{ready=false;}finally{clearTimeout(timeout);if(phase==='home')paint();}
}
function home(){
 const s=C.summarize(deck,progress,C.today());const resume=read(ROUND);
 const latestCount=data.vocabulary.filter(word=>word.batchAdded===data.batchId).length;
 const latestItems=deck.filter(item=>item.batchAdded===data.batchId||item.touchedBatches?.includes(data.batchId));
 const revisitedCount=new Set(latestItems.filter(item=>item.batchAdded!==data.batchId).map(item=>item.wordId)).size;
 const seenCount=latestItems.filter(item=>progress.items[item.id]?.attempts>0).length;
 return `<div class="game-hero"><div class="game-kicker">SPEAK & GROW · 开口练习</div><h1 class="game-title">开口打地鼠</h1><p class="game-subtitle">可以先听示范，也可以直接读。读完稍作停顿，自动换下一个词。</p></div>
 <div class="game-stats"><div class="game-stat"><b>${new Set(deck.map(x=>x.wordId)).size}</b><span>可练词条</span></div><div class="game-stat"><b>${s.verified||0}</b><span>发音通过</span></div><div class="game-stat"><b>${s.practiceAttempts||0}</b><span>跟读次数</span></div></div>
 ${latestCount?`<section class="game-latest game-panel"><div><span class="game-kicker">本次更新 · ${esc(data.batchId)}</span><h2>${latestCount} 个新词与短语，先从这一批练起</h2><p>另有 ${revisitedCount} 个旧词在本批再次出现；已练过 ${seenCount} / ${latestItems.length} 个发音目标。示范按需听，读完自动换词；未达标的词留待巩固，练过不等于掌握。</p></div>${btn('latest','练本次更新 · 连续读词','class="game-start primary"')}</section>`:''}
 ${!ready?'<p class="game-banner warning">专业评分尚未接通，可先听读、录音回听。跟读试玩只记练习，不判定发音达标或晋级。</p>':'<p class="game-banner">发音评分已就绪。每局点一次开始，读完自动评分并换词；未达标留待巩固，不会卡在同一词。</p>'}
 <section class="game-panel"><h2>今天，练哪一组？</h2><div class="game-modes">${[['batch',`本次更新 ${esc(data.batchId||'')}`],['all','全部词库'],['group','按主题练'],['due','今日巩固'],['weak','薄弱词']].map(([k,t])=>btn('mode',t,`class="game-mode ${mode===k?'is-selected':''}" aria-pressed="${mode===k}" data-mode="${k}"`)).join('')}</div>
 <div class="game-config">${mode==='group'?`<label>练习主题<select id="game-group">${groups.map(g=>`<option ${g===group?'selected':''}>${esc(g)}</option>`).join('')}</select></label>`:''}<label>提示方式<select id="game-training"><option value="warmup" ${training==='warmup'?'selected':''}>跟读热身 · 显示中文</option><option value="independent" ${training==='independent'?'selected':''}>独立朗读 · 隐藏中文</option></select></label></div>
 <p class="small">每局 10 题，完成后可以继续开新一局，练习次数不限。不同词形分别练，较长短语完整显示。</p>
 <div class="game-actions">${ready?btn('challenge','开始连续读词 · 自动评分','class="game-start primary"'):''}${btn('start','不评分 · 连续跟读',ready?'':'class="game-start"')}${resume?.queue?.length?btn('resume','继续上次练习'):''}</div>
 </section>
 <section class="game-stages game-panel" aria-label="学习阶段"><h2>怎样从新词练到会用？</h2><ol><li><strong>1 听读热身</strong><span>听示范、看词义，先熟悉发音。</span></li><li><strong>2 独立朗读</strong><span>遮住中文自己读；只有正式评分通过才记发音成绩。</span></li><li><strong>3 情景运用</strong><span>把词放进课堂句子和对话，不把发音分当作完整掌握。</span></li><li><strong>4 间隔巩固</strong><span>按 1、3、7、14、30 天回来复习。</span></li></ol></section>
 <details class="game-settings game-panel"><summary>我的已学范围</summary><p class="small">新资料自动进入全部词库。勾选学过的分类后，今日巩固和薄弱词只从这些分类出题。</p><div class="game-learned">${groups.map(g=>`<label><input type="checkbox" data-learned="${esc(g)}" ${prefs.learnedGroups.includes(g)?'checked':''}> ${esc(g)}</label>`).join('')}</div></details>
 <details class="game-settings game-panel"><summary>游戏规则与学习记录</summary><p>读完自动换词，只有正式评分通过才命中；未达标的词记入薄弱词，下轮再练。完成一局得 1 星，通过 70% 得 2 星，80% 首次独立通过得 3 星。评分结果只是本次练习参考。</p><p>独立通过后按 1、3、7、14、30 天复习，同一天重复通过不连续升级。有提示完成会单独记录。稍后练的词会回到薄弱词列表。</p><p class="small">记录保存在当前浏览器，iPhone 与 iPad 暂不自动同步。导出后可以在另一设备导入；旧版自测记录保持独立。</p><div class="game-actions">${btn('export','导出游戏记录')}<label class="button">导入游戏记录<input id="game-import" type="file" accept=".json,application/json" hidden></label></div></details>`;
}
function card(){
 const item=current();if(!item)return resultView();
 const speaking=['loading','speaking'].includes(speech.snapshot().phase);
 const micLabel=phase==='recording'?'正在听 · 点按暂停':phase==='permission'?'正在开启麦克风':phase==='demo'?'正在播放示范':phase==='buffer'?'准备开口':phase==='encoding'||phase==='assessing'?(practice?'正在记录练习':'正在评分'):completedCurrent?'点麦克风读下一词':'点麦克风，直接读';
 return `<div class="game-progress"><span>${practice?'跟读试玩':'发音闯关'} · ${esc(item.group)}</span>${busy()?btn('pause','暂停'):btn('leave','保存退出')}<b>第 ${index+1} / ${queue.length} 题</b></div><div class="game-progress-track" role="progressbar" aria-label="本局进度" aria-valuemin="0" aria-valuemax="${queue.length}" aria-valuenow="${index}"><i style="width:${index/queue.length*100}%"></i></div>
 <section class="game-arena ${phase==='hit'?'hit':''} game-reading"><div class="game-card"><span class="game-kicker">${item.kind==='word'?'WORD · 单词':'PHRASE · 短语'}</span><h1 class="game-word" lang="en-US">${esc(item.text)}</h1>${item.ipa?`<p class="game-ipa" lang="en-US">${esc(item.ipa)}</p>`:''}${item.speechNote?`<p class="small">${esc(item.speechNote)}</p>`:''}${item.text==='bedroom'?'<p class="game-audio-credit">本词真人示范：<a href="https://commons.wikimedia.org/wiki/File:En-us-bedroom.ogg" target="_blank" rel="noopener noreferrer">Dvortygirl / Wikimedia Commons 原音</a> · <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 3.0</a></p>':''}${training==='warmup'||translationShown?`<p class="game-translation">${esc(item.zh)}</p>`:btn('reveal-translation','查看中文（计入提示）',busy()?'disabled':'class="game-reveal"')}</div>
 <div class="game-demo-actions">${btn('listen','▶ 听示范',canListen()?'':'disabled')}${btn('slow','慢速示范',canListen()?'':'disabled')}${speaking?btn('stop-listen','停止示范'):''}</div><p id="game-speech-status" class="small" aria-live="polite">${esc(speech.snapshot().message||'')}</p>
 ${scoreView()}<div class="game-voice-controls"><div class="game-voice-control">${btn('record',icon('mic'),`class="game-mic ${phase==='recording'?'recording':''}" aria-label="${micLabel}" ${!canUseMic()||speaking?'disabled':''}`)}<span>${micLabel}</span></div>${replayControl()}</div>
 ${blob?`<p class="game-replay-target">可回听 · <span lang="en">${esc(recordedText)}</span></p>`:''}
 <p class="game-reading-hint">${practice?'读完自动换词 · 本轮不评分':'读完自动评分、下一词 · 不必逐词点按钮'}</p>
 <div class="game-skip-row">${btn('skip',completedCurrent?'下一个':'跳过')}</div></section>
 <details class="game-reading-notice"><summary>录音与练习说明</summary><p>${practice?'本轮不上传、不评分，只记练习。':'每次录音最长 12 秒，将发送到腾讯云评分；未达标的词留待巩固。'}点回放会暂停练习并关闭麦克风；听完后点麦克风继续。录音仅临时保留在本页，离开后不保存。</p></details>`;
}
function resultView(){
 const passed=results.filter(x=>x.outcome==='pass').length,first=results.filter(x=>x.outcome==='pass'&&!x.hinted&&x.tries===1).length;
 const stars=practice?0:passed>=queue.length*.7?(first>=queue.length*.8?3:2):1;
 const weak=results.filter(x=>!['pass','practice'].includes(x.outcome));
 const prompted=results.filter(x=>x.outcome==='pass'&&x.hinted);
 const review=results.filter(x=>x.outcome!=='pass'||x.hinted);
 const batchSources=new Set((data.sources||[]).filter(source=>source.batchId===data.batchId).map(source=>source.id));
 const batchUnits=new Set((data.units||[]).filter(unit=>unit.sources?.some(id=>batchSources.has(id))).map(unit=>unit.id));
 const scenario=[...(data.scenarios||[])].reverse().find(item=>item.unitIds?.some(id=>batchUnits.has(id)));
 const scenarioHref=scenario?`#scenarios/${encodeURIComponent(scenario.id)}`:'#scenarios/weekend-chat';
 return `<section class="game-panel game-result"><div class="game-kicker">这一局，给开口的自己一点掌声</div><h1>${practice?'跟读练习完成':'本轮闯关完成'}</h1>${practice?'<p>本轮是跟读试玩，未进行发音评分；跟读完成不代表已经掌握。</p>':`<div class="game-stars" aria-label="${stars} 星">${'★'.repeat(stars)}${'☆'.repeat(3-stars)}</div><p>${passed} / ${queue.length} 个目标发音通过 · ${stars>=2?'本轮发音表现达标；还要在情景中使用并按时复习。':'继续新词也可以，薄弱词稍后再练。'}</p>`}<p>本轮${practice?'跟读 '+results.filter(x=>x.outcome==='practice').length:'通过 '+passed} 个目标。${practice?'可以针对本组词独立再读。':`${weak.length} 个未达标或未评分，${prompted.length} 个有提示通过、待独立再读。`}</p>${weak.length?`<h2>留待巩固</h2><ul class="game-weak-list">${weak.map(x=>`<li lang="en">${esc(deck.find(d=>d.id===x.id)?.text)} <span>${x.outcome==='uncertain'?'未评分，不算读错':x.outcome==='skip'?'稍后再读':'未达标'}</span></li>`).join('')}</ul>`:''}${practice?'<p class="game-next-step">下一阶段：遮住中文，试着不听示范独立朗读。评分可用时，通过后才会计入发音进度。</p>':'<p class="game-next-step">下一阶段：在情景中用自己的话说一句，再按到期安排巩固。</p>'}<div class="game-actions">${btn('again','继续下一组新词 →','class="game-start primary"')}${practice?btn('independent-next',ready?'本组独立朗读 · 自动评分':'本组独立朗读 · 不评分'):review.length?btn('review-round','复练本组需巩固词'):''}<a class="button" href="${scenarioHref}">情景运用 · ${esc(scenario?.title||'开口练习')}</a>${btn('home','返回游戏首页')}</div></section>`;
}
function paint(){if(!host?.isConnected)return;host.innerHTML=controlsStyle+(storageOK?'':'<p class="game-banner warning">浏览器未能保存记录，请先导出备份。</p>')+(phase==='home'?home():phase==='result'?resultView():card())+(phase==='result'&&blob?`${scoreView()}<div class="game-voice-controls">${replayControl()}</div><p class="game-replay-target">最后一次录音 · ${esc(recordedText)}</p>`:'')+`<p id="game-feedback" class="game-feedback ${phase==='hit'?'success':''}" role="status" aria-live="polite">${esc(status)}</p>`;}
function playbackSession(){
 // Safari may keep its recording route after microphone use. Feature-detect
 // the playback category and restore the previous category when replay stops.
 try{const session=root.navigator?.audioSession;if(session){previousAudioSession=session.type;session.type='playback';}}catch{previousAudioSession=null;}
}
function stopReplay(){
 clearTimeout(replayTimer);replayTimer=null;
 if(replay){replay.onended=null;replay.onerror=null;replay.onplaying=null;replay.ontimeupdate=null;replay.onpause=null;replay.pause();replay.remove?.();}
 replay=null;replaying=false;
 if(previousAudioSession!==null){try{const session=root.navigator?.audioSession;if(session?.type==='playback')session.type=previousAudioSession;}catch{}previousAudioSession=null;}
}
// Clearing playback between targets must not release the prepared iOS microphone session.
function clearPlayback({discardRecording=true}={}){
 if(speechWait){const wait=speechWait;speechWait=null;wait.reject(cancelled());}
 speech.stop('');stopReplay();
 if(discardRecording){if(blobUrl)URL.revokeObjectURL(blobUrl);blobUrl=null;blob=null;recordedText='';lastAssessment=null;}
}
function cancelPending({keepRecording=false}={}){
 continuous=false;requestSerial++;abort?.abort();abort=null;
 clearTimeout(nextTimer);nextTimer=null;
 if(delayReject){const reject=delayReject;delayReject=null;reject(cancelled());}
 clearPlayback({discardRecording:!keepRecording});recorder.release();
}
function persistRound(){
 if(!queue.length)return;
 // Commit every completed target before feedback, without turning retries into passes.
 const savedIndex=index+(completedCurrent?1:0);
 if(savedIndex>=queue.length){try{localStorage.removeItem(ROUND);}catch{storageOK=false;}return;}
 store(ROUND,{version:1,queue:queue.map(x=>x.id),index:savedIndex,results,roundId,practice,training,mode,group,hinted:completedCurrent?training==='warmup':hinted,tries:completedCurrent?0:tries});
}
function delay(ms,serial){return new Promise((resolve,reject)=>{
 if(!valid(serial)){reject(cancelled());return;}
 delayReject=reject;nextTimer=setTimeout(()=>{nextTimer=null;delayReject=null;valid(serial)?resolve():reject(cancelled());},ms);
});}
function finishTarget(){
 index++;completedCurrent=false;hinted=training==='warmup';translationShown=false;tries=0;status='';
 phase=index>=queue.length?'result':'question';persistRound();
}
function pauseFlow(message){
 if(completedCurrent)finishTarget();
 cancelPending({keepRecording:true});if(phase!=='home'&&phase!=='result')phase='question';
 status=message;persistRound();paint();
}
function startRound(isPractice=true,targets=null){
 cancelPending();practice=isPractice;queue=targets?targets.slice():C.makeQueue(deck,progress,{mode,batchId:data.batchId,group:group||groups[0],learnedGroups:prefs.learnedGroups,day:C.today(),limit:10,random:Math.random});
 if(!queue.length){phase='home';status=mode==='weak'?'已学范围内还没有薄弱词，可以先练一局。':mode==='due'?'当前没有待练词。请勾选已学范围，或从全部词库开始。':'这一组暂时没有可练内容。';paint();return;}
 index=0;results=[];roundId=crypto.randomUUID();hinted=training==='warmup';translationShown=false;tries=0;completedCurrent=false;phase='question';status='可以先听示范，也可以直接读。点一次开始后，读完稍作停顿，自动换下一个词。';persistRound();paint();host?.scrollIntoView({block:'start'});
}
function restoreRound(r){
 if(!r||r.version!==1||!Array.isArray(r.queue)||!r.queue.length||r.queue.length>10||!Number.isInteger(r.index)||r.index<0||r.index>=r.queue.length)throw Error('上次练习无法恢复，学习记录仍保留。请开始新的一局。');
 const qs=r.queue.map(id=>deck.find(d=>d.id===id));if(qs.some(x=>!x))throw Error('词库已更新，请开始新的一局。已完成记录仍保留。');
 cancelPending();queue=qs;index=r.index;results=Array.isArray(r.results)?r.results.slice(0,index).map(x=>({id:String(x.id),outcome:['pass','retry','uncertain','practice','skip'].includes(x.outcome)?x.outcome:'skip',hinted:!!x.hinted,tries:Number(x.tries)||0})):[];
 practice=r.practice===true;training=r.training==='independent'?'independent':'warmup';mode=['batch','all','group','due','weak'].includes(r.mode)?r.mode:mode;if(groups.includes(r.group))group=r.group;roundId=String(r.roundId||crypto.randomUUID());hinted=training==='warmup'||!!r.hinted;translationShown=false;tries=Math.max(0,Number(r.tries)||0);completedCurrent=false;phase='question';status='已回到上次的位置。准备好后点开始，麦克风才会开启。';paint();host?.scrollIntoView({block:'start'});
}
function resume(){
 try{const r=read(ROUND);if(r?.practice!==true&&(!ready||!token||Date.now()>=expires)){
  if(!ready){status='上次闯关成绩已保存。评分服务尚未就绪，接通后可继续原来的位置。';paint();return;}
  connectView(r);return;
 }restoreRound(r);}catch(e){status=e.message;paint();}
}
function note(outcome){progress=C.recordAttempt(progress,current(),{outcome,hinted,day:C.today(),now:Date.now()});save();}
function advance(outcome){
 if(!current())return;
 if(outcome==='pass'){if(!completedCurrent)return;}else{note(outcome);results.push({id:current().id,outcome,hinted,tries});}
 cancelPending();finishTarget();paint();host?.querySelector('h1')?.setAttribute('tabindex','-1');host?.querySelector('h1')?.focus({preventScroll:true});
}
function skipTarget(){
 if(!current()||phase==='home'||phase==='result')return;
 const keepGoing=continuous;
 // Invalidate pending assessment before changing the target. A completed score
 // already belongs to this card: never also skip the following card.
 cancelPending({keepRecording:true});
 if(!completedCurrent){note('skip');results.push({id:current().id,outcome:'skip',hinted,tries});}
 finishTarget();paint();
 if(keepGoing&&phase!=='result')record();
}
function useMic(){
 if(!canUseMic())return;
 if(phase==='recording'){pauseFlow('已暂停，麦克风已关闭。点麦克风继续读。');return;}
 if(completedCurrent){cancelPending({keepRecording:true});finishTarget();paint();if(phase==='result')return;}
 record();
}
function playRecording(){
 if(!canReplay())return;
 if(replaying){stopReplay();status='回放已停止。点麦克风继续读。';paint();return;}
 // Keep a completed card visible while replaying it. The microphone action
 // advances it once; pending timers and stale assessment responses are cancelled.
 cancelPending({keepRecording:true});if(phase!=='result')phase='question';
 const player=new Audio(blobUrl);replay=player;replaying=true;
 player.muted=false;player.volume=1;player.preload='auto';player.playsInline=true;player.controls=true;
 player.setAttribute?.('playsinline','');player.setAttribute?.('aria-label',`我的录音：${recordedText}`);player.className='english-recording-player';
 const settle=failed=>{if(replay!==player)return;stopReplay();status=failed?'回放没有正常播放，请再点一次回放。若仍无声，请检查设备媒体音量和蓝牙输出。':'回放结束。点麦克风继续读。';paint();};
 let advanced=0;
 const watch=()=>{clearTimeout(replayTimer);replayTimer=setTimeout(()=>{if(replay===player)settle(true);},5000);};
 const update=()=>{
  if(replay!==player||player.paused)return;
  const at=Number(player.currentTime)||0;
  if(at>advanced+.02){advanced=at;watch();}
  // The media event and currentTime, not a resolved play() Promise, establish playback.
  status=`正在回放 ${recordedText} · ${at.toFixed(1)} 秒。麦克风已关闭。`;
  const line=host?.querySelector('#game-feedback');if(line)line.textContent=status;
 };
 player.onplaying=()=>{if(replay!==player)return;watch();update();};player.ontimeupdate=update;
 player.onpause=()=>{if(replay!==player||player.ended)return;clearTimeout(replayTimer);replayTimer=null;status='回放已暂停，可用下方播放器继续，或点麦克风继续读。';const line=host?.querySelector('#game-feedback');if(line)line.textContent=status;};
 player.onended=()=>settle(!(Number(player.currentTime)>.05));player.onerror=()=>settle(true);
 status=`正在准备回放 ${recordedText}…`;paint();
 // Keep the native player outside the re-rendered card, with a real seek bar.
 host?.insertAdjacentElement?.('afterend',player);playbackSession();watch();
 try{Promise.resolve(player.play()).catch(()=>settle(true));}catch{settle(true);}
}
function demo(serial,slow=false){
 if(!valid(serial))return Promise.reject(cancelled());
 hinted=true;phase='demo';status='听完示范后，自动轮到你读。';persistRound();paint();
 return new Promise((resolve,reject)=>{
  speechWait={key:current().id,resolve,reject};
  speech.play({key:current().id,label:current().text,text:current().text,mode:slow?'slow':'normal'});
 });
}
function assertConnection(){if(!ready||!token||Date.now()>=expires)throw Error('评分连接已过期。本次没有上传录音，请保存退出后重新连接。');}
async function captureAudio(serial,keepSession){
 const item=current();clearPlayback({discardRecording:false});
 const capture=await recorder.start({autoStop:true,keepSession,kind:item.kind});
 if(!valid(serial))throw cancelled();
 phase='recording';status='轮到你了。正常朗读，读完稍作停顿，会自动结束录音。';paint();
 // Attach both handlers together: NO_SPEECH deliberately rejects result and exposes no Blob.
 const [audio,completion]=await Promise.all([capture.result,capture.completion]);
 if(!valid(serial))throw cancelled();
 if(completion.reason==='cancelled')throw cancelled();
 if(completion.speechDetected===false||completion.reason==='no_speech')throw Object.assign(Error('这次没有听到清楚的朗读，不上传、不算读错。准备好再继续。'),{code:'NO_SPEECH'});
 // A noisy room may prevent a clean silence boundary. The recorder still ends
 // at 12 seconds; send that bounded recording once and let the gateway judge it.
 // An energy detection or a timeout alone never counts as a pronunciation pass.
 phase='encoding';status=completion.reason==='limit'?(practice?'已自动结束录音，正在记录本次练习…':'已自动结束录音，正在准备评分…'):'正在整理这次录音…';paint();
 const wav=await recorder.encode(audio);if(!valid(serial))throw cancelled();
 // Replay the exact decoded PCM used for assessment, not the browser-specific
 // MediaRecorder container (MP4/WebM), whose playback support can differ.
 if(blobUrl)URL.revokeObjectURL(blobUrl);
 blob=new Blob([wav.bytes],{type:'audio/wav'});blobUrl=URL.createObjectURL(blob);recordedText=item.text;lastAssessment=null;
 if(wav.duration<.25||wav.rms<.002)throw Error('这次声音太短或太轻，没算读错。靠近一点，再继续。');
 return wav;
}
async function assess(wav,serial){
 assertConnection();const item=current();phase='assessing';status='正在听你的发音…';paint();
 const controller=new AbortController();abort=controller;const timer=setTimeout(()=>controller.abort(),25000);
 try{
  let str='';for(const b of wav.bytes)str+=String.fromCharCode(b);
  const result=await jsonFetch('/assess',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},signal:controller.signal,body:JSON.stringify({targetId:item.targetId,text:item.text,kind:item.kind,audio:{base64:btoa(str),format:'wav'},attemptId:crypto.randomUUID()})});
  if(!valid(serial))throw cancelled();
  if(!['pass','retry','uncertain'].includes(result.status))throw Error('这次评分未能确认，已暂停；没有记为发音错误。');
  return result;
 }finally{clearTimeout(timer);if(abort===controller)abort=null;}
}
function errorMessage(e){
 if(e.code==='NO_SPEECH')return '这次没有听到清楚的朗读，已暂停。不上传、不算读错，准备好再继续。';
 if(e.code==='DEMO_UNAVAILABLE')return '示范声音未能播放，已暂停。可以重新点「听示范」，或点「直接读」继续，不必等待示范。';
 if(e.name==='AbortError')return '评分等待较久，已暂停。这次不算读错，也不会自动重试上传；准备好再继续。';
 return e.message||'这次未能完成评测，已暂停，没有记为发音错误。';
}
async function record({example=null}={}){
 if(busy()||!current()||document.hidden)return;
 if(!practice){try{assertConnection();}catch(e){pauseFlow(errorMessage(e));return;}}
 clearPlayback({discardRecording:false});abort?.abort();const serial=++requestSerial;continuous=true;
 phase='permission';status='请允许麦克风。每次朗读后稍作停顿，会自动结束录音。';
 // Keep this call in the click stack: AudioContext.resume must precede await on iOS.
 let prepared,exampleDone;try{prepared=recorder.prepare();if(example)exampleDone=demo(serial,example==='slow');}catch(e){pauseFlow(errorMessage(e));return;}paint();
 try{
  // Both microphone preparation and optional playback begin in the user's click stack.
  // Recording stays disabled until the entire example and its tail buffer have ended.
  await Promise.all([prepared,exampleDone]);if(!valid(serial))return;
  while(valid(serial)&&continuous&&current()){
   if(!practice)assertConnection();
   if(!valid(serial))return;
   phase='buffer';status='轮到你了，准备开口…';paint();await delay(650,serial);
   const wav=await captureAudio(serial,true);if(!valid(serial))return;
   const result=practice?{status:'practice',feedback:'已完成本词跟读，自动下一词。本轮未评分，不代表发音已通过。'}:await assess(wav,serial);if(!valid(serial))return;
   tries++;note(result.status);
   const validScore=!['practice','uncertain'].includes(result.status)&&typeof result.score==='number'&&Number.isFinite(result.score)&&result.score>=0&&result.score<=100;
   lastAssessment={text:current().text,outcome:result.status,score:validScore?Math.round(result.score):null,feedback:result.feedback||''};
   const score=typeof result.score==='number'&&Number.isFinite(result.score)&&result.score>=0&&result.score<=100?`本次评分 ${Math.round(result.score)}/100 · `:'';
   status=score+(result.feedback||(result.status==='pass'?'读得清楚，命中！':'再练一次，会更清楚。'));
   if(result.status==='retry')status+=' 未达标，已留待巩固；自动下一词。';
   if(result.status==='uncertain')status=(result.feedback||'本次未能确认评分。')+' 不算读错，留待再读；自动下一词。';
   completedCurrent=true;results.push({id:current().id,outcome:result.status,hinted,tries});phase=result.status==='pass'?'hit':'feedback';persistRound();paint();
   await delay(1300,serial);if(!valid(serial))return;
   clearPlayback({discardRecording:false});finishTarget();paint();
   if(phase==='result'){cancelPending({keepRecording:true});paint();return;}
  }
 }catch(e){if(!valid(serial))return;pauseFlow(errorMessage(e));}
}
function connectView(savedRound=null,targets=null){
 if(!ready)return;
 if(token&&Date.now()<expires){if(savedRound)restoreRound(savedRound);else startRound(false,targets);return;}
 cancelPending();phase='home';paint();const panel=document.createElement('section');panel.className='game-panel';panel.innerHTML=`<h2>连接发音评分</h2><p>${esc(config.cloudNotice||'短录音将发送到腾讯云做本次评测。')}</p><p class="small">使用你已解锁的英语栏目自动连接，无需再输入评分口令。你点击开始连续闯关后，每题读完会自动评分并进入下一题；暂停或切到后台立即关闭麦克风。服务异常不计为发音错误。</p><form id="game-connect"><label><input type="checkbox" id="game-consent" required> 同意将本次练习的短录音发送给腾讯云评分</label><button class="game-start" type="submit">同意并连接评分</button><p id="game-connect-status" role="status"></p></form>`;
 host.prepend(panel);panel.querySelector('form').addEventListener('submit',async e=>{
 e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;const serial=++requestSerial;abort=new AbortController();const timeout=setTimeout(()=>abort?.abort(),8000);
 try{const password=await siteCredential();if(serial!==requestSerial)return;const result=await jsonFetch('/session',{method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,body:JSON.stringify({password})});if(serial!==requestSerial)return;
 if(typeof result.token!=='string'||!Number.isFinite(Date.parse(result.expiresAt)))throw Error('评分服务返回了无效连接。');token=result.token;expires=Date.parse(result.expiresAt);if(savedRound)restoreRound(savedRound);else startRound(false,targets);
 }catch(err){if(serial!==requestSerial)return;panel.querySelector('#game-connect-status').textContent=err.name==='AbortError'?'连接超时，请稍后再试。':err.status===401?'网站解锁状态与评分服务尚未同步，请稍后再试。':err.message;button.disabled=false;}finally{clearTimeout(timeout);}
 });panel.querySelector('#game-consent').focus();
}
function handle(e){
 const b=e.target.closest('[data-game]');if(!b||b.disabled)return;
 switch(b.dataset.game){
 case'mode':mode=b.dataset.mode;status='';paint();break;
 case'latest':mode='batch';training='warmup';if(ready)connectView();else startRound(true);break;
 case'start':startRound(true);break;
 case'independent-next':{const targets=queue.slice();training='independent';if(ready)connectView(null,targets);else startRound(true,targets);break;}
 case'review-round':{const ids=new Set(results.filter(x=>x.outcome!=='pass'||x.hinted).map(x=>x.id));const targets=queue.filter(x=>ids.has(x.id));training='independent';if(ready)connectView(null,targets);else startRound(true,targets);break;}
 case'challenge':connectView();break;
 case'resume':resume();break;
 case'reveal-translation':if(!busy()&&current()){hinted=true;translationShown=true;status='已查看中文，本题会记为有提示练习。';persistRound();paint();}break;
 case'listen':case'slow':if(canListen()&&current()){
  const example=b.dataset.game==='slow'?'slow':'normal';
  if(continuous){pauseFlow('先听示范，再继续读本词。');record({example});}
  else{hinted=true;persistRound();stopReplay();speech.play({key:current().id,label:current().text,text:current().text,mode:example});paint();}
 }break;
 case'stop-listen':if(continuous)pauseFlow('练习已暂停，麦克风已关闭。准备好后继续。');else{speech.stop('');paint();}break;
 case'record':useMic();break;
 case'pause':pauseFlow('练习已暂停，麦克风已关闭。准备好后继续；已通过的成绩已保存。');break;
 case'replay':playRecording();break;
 case'practiced':if(practice&&!busy())advance('practice');break;
 case'skip':skipTarget();break;
 case'leave':pauseFlow('已暂停，已完成的学习记录已保存。');clearPlayback();phase='home';paint();break;
 case'home':cancelPending();phase='home';status='';paint();break;
 case'again':if(!practice&&(!token||Date.now()>=expires)){phase='home';paint();connectView();}else{startRound(practice);if(current())record();}break;
 case'export':{const url=URL.createObjectURL(new Blob([JSON.stringify({type:'andy-english-game',version:1,progress,prefs,exportedAt:new Date().toISOString()},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='英语游戏记录_'+C.today()+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);break;}
 }
}
async function change(e){
 if(e.target.id==='game-group')group=e.target.value;
 if(e.target.id==='game-training')training=e.target.value;
 if(e.target.dataset.learned){prefs.learnedGroups=[...host.querySelectorAll('[data-learned]:checked')].map(x=>x.dataset.learned);store(PREFS,prefs);}
 if(e.target.id==='game-import'){
 try{const file=e.target.files[0];if(!file)return;if(file.size>1500000)throw Error('备份过大，请选择游戏导出的记录。');const d=JSON.parse(await file.text());if(d.type!=='andy-english-game'||d.version!==1||d.progress?.schemaVersion!==C.SCHEMA_VERSION||!d.progress.items||Array.isArray(d.progress.items))throw Error('请使用游戏记录备份；自测记录在复习自测页面导入。');const incoming=C.sanitizeProgress(d.progress,deck);
 for(const [id,r]of Object.entries(incoming.items)){const old=progress.items[id];if(!old||(r.last||'')>(old.last||'')||((r.last||'')===(old.last||'')&&r.attempts>old.attempts))progress.items[id]=r;}
 prefs.learnedGroups=[...new Set([...prefs.learnedGroups,...(Array.isArray(d.prefs?.learnedGroups)?d.prefs.learnedGroups.filter(g=>groups.includes(g)):[])])];save();store(PREFS,prefs);status='已合并较新的游戏记录。';
 }catch(err){status=err.message||'导入失败，原记录已保留。';}paint();
 }
}
function unmount(){if(!initialized)return;if(completedCurrent)finishTarget();if(phase!=='home'&&phase!=='result')persistRound();cancelPending();host=null;phase='home';token='';expires=0;}
root.addEventListener('pagehide',unmount);
root.addEventListener('pageshow',e=>{if(e.persisted&&initialized&&document.getElementById('english-game')){host=document.getElementById('english-game');phase='home';status='欢迎回来，已完成的记录已保留。';paint();}});
root.document.addEventListener('visibilitychange',()=>{if(document.hidden&&initialized){pauseFlow('练习已暂停，麦克风已关闭。回到页面后，请亲自点继续。');}});
root.EnglishGame={view,mount,unmount};
})(globalThis);
