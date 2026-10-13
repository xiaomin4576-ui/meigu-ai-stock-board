/* Continuous voice practice. Only a confirmed gateway pass can score a hit. */
(function(root){
'use strict';
const C=root.EnglishGameCore, STORE='andy-english-game-v1',PREFS='andy-english-game-prefs-v1',ROUND='andy-english-game-round-v1';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let deck=[],groups=[],progress,prefs={learnedGroups:[]},config={},host=null,data,initialized=false,storageOK=true;
let queue=[],index=0,results=[],roundId='',phase='home',status='',mode='all',group='',practice=true,training='warmup';
let hinted=false,translationShown=false,tries=0,requestSerial=0,abort=null,nextTimer=null,blob=null,blobUrl=null,replay=null,token='',expires=0,ready=false,healthChecked=false;
let continuous=false,passedCurrent=false,delayReject=null,speechWait=null,manualDemoKey=null,manualDemoReady=null;
const current=()=>queue[index],busy=()=>continuous||['permission','demo','buffer','recording','encoding','assessing','hit'].includes(phase);
const recorder=root.EnglishGameAudio.createRecorder();
const cancelled=()=>Object.assign(Error('练习已暂停。'),{code:'CANCELLED'});
const valid=serial=>serial===requestSerial&&!document.hidden&&!!host?.isConnected;
const speech=root.EnglishSpeech.createController({synth:root.speechSynthesis,Utterance:root.SpeechSynthesisUtterance,onChange:s=>{
  if(speechWait&&s.key===speechWait.key){
   if(s.phase==='done'){const wait=speechWait;speechWait=null;wait.resolve();}
   else if(s.phase==='error'||s.phase==='idle'){const wait=speechWait;speechWait=null;wait.reject(Object.assign(Error(s.message||'示范未能播放。'),{code:'DEMO_UNAVAILABLE'}));}
  }
  if(manualDemoKey&&s.key===manualDemoKey&&s.phase==='done'){manualDemoReady=manualDemoKey;manualDemoKey=null;}
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
 return `<div class="game-hero"><div class="game-kicker">SPEAK & GROW · 开口练习</div><h1 class="game-title">开口打地鼠</h1><p class="game-subtitle">听一遍，自己说。把每一次开口，变成下一次的熟练。</p></div>
 <div class="game-stats"><div class="game-stat"><b>${new Set(deck.map(x=>x.wordId)).size}</b><span>可练词条</span></div><div class="game-stat"><b>${s.verified||0}</b><span>发音通过</span></div><div class="game-stat"><b>${s.practiceAttempts||0}</b><span>跟读次数</span></div></div>
 ${latestCount?`<section class="game-latest game-panel"><div><span class="game-kicker">本次更新 · ${esc(data.batchId)}</span><h2>${latestCount} 个新词与短语，先从这一批练起</h2><p>另有 ${revisitedCount} 个旧词在本批再次出现；已练过 ${seenCount} / ${latestItems.length} 个发音目标。先热身，再独立朗读和情景运用；练过不等于掌握。</p></div>${btn('latest','练本次更新 · 开始热身','class="game-start primary"')}</section>`:''}
 ${!ready?'<p class="game-banner warning">专业评分尚未接通，可先听读、录音回听。跟读试玩只记练习，不判定发音达标或晋级。</p>':'<p class="game-banner">发音评分已就绪。每局点一次开始，读完自动评分，达标自动进入下一词。</p>'}
 <section class="game-panel"><h2>今天，练哪一组？</h2><div class="game-modes">${[['batch',`本次更新 ${esc(data.batchId||'')}`],['all','全部词库'],['group','按主题练'],['due','今日巩固'],['weak','薄弱词']].map(([k,t])=>btn('mode',t,`class="game-mode ${mode===k?'is-selected':''}" aria-pressed="${mode===k}" data-mode="${k}"`)).join('')}</div>
 <div class="game-config">${mode==='group'?`<label>练习主题<select id="game-group">${groups.map(g=>`<option ${g===group?'selected':''}>${esc(g)}</option>`).join('')}</select></label>`:''}<label>提示方式<select id="game-training"><option value="warmup" ${training==='warmup'?'selected':''}>跟读热身 · 显示中文</option><option value="independent" ${training==='independent'?'selected':''}>独立朗读 · 隐藏中文</option></select></label></div>
 <p class="small">每局 10 题，完成后可以继续开新一局，练习次数不限。不同词形分别练，较长短语完整显示。</p>
 <div class="game-actions">${ready?btn('challenge','开启发音闯关','class="game-start primary"'):''}${btn('start','开始跟读试玩',ready?'':'class="game-start"')}${resume?.queue?.length?btn('resume','继续上次练习'):''}</div>
 </section>
 <section class="game-stages game-panel" aria-label="学习阶段"><h2>怎样从新词练到会用？</h2><ol><li><strong>1 听读热身</strong><span>听示范、看词义，先熟悉发音。</span></li><li><strong>2 独立朗读</strong><span>遮住中文自己读；只有正式评分通过才记发音成绩。</span></li><li><strong>3 情景运用</strong><span>把词放进课堂句子和对话，不把发音分当作完整掌握。</span></li><li><strong>4 间隔巩固</strong><span>按 1、3、7、14、30 天回来复习。</span></li></ol></section>
 <details class="game-settings game-panel"><summary>我的已学范围</summary><p class="small">新资料自动进入全部词库。勾选学过的分类后，今日巩固和薄弱词只从这些分类出题。</p><div class="game-learned">${groups.map(g=>`<label><input type="checkbox" data-learned="${esc(g)}" ${prefs.learnedGroups.includes(g)?'checked':''}> ${esc(g)}</label>`).join('')}</div></details>
 <details class="game-settings game-panel"><summary>游戏规则与学习记录</summary><p>发音闯关：读清楚才命中。完成一局得 1 星，通过 70% 得 2 星，80% 首次独立通过得 3 星。评分结果只是本次练习参考。</p><p>独立通过后按 1、3、7、14、30 天复习，同一天重复通过不连续升级。有提示完成会单独记录。稍后练的词会回到薄弱词列表。</p><p class="small">记录保存在当前浏览器，iPhone 与 iPad 暂不自动同步。导出后可以在另一设备导入；旧版自测记录保持独立。</p><div class="game-actions">${btn('export','导出游戏记录')}<label class="button">导入游戏记录<input id="game-import" type="file" accept=".json,application/json" hidden></label></div></details>`;
}
function card(){
 const item=current();if(!item)return resultView();
 const speaking=['loading','speaking'].includes(speech.snapshot().phase);
 return `<div class="game-progress"><span>${practice?'跟读试玩':'发音闯关'} · ${esc(item.group)}</span>${busy()?btn('pause','暂停'):btn('leave','保存退出')}<b>第 ${index+1} / ${queue.length} 题</b></div><div class="game-progress-track" role="progressbar" aria-label="本局进度" aria-valuemin="0" aria-valuemax="${queue.length}" aria-valuenow="${index}"><i style="width:${index/queue.length*100}%"></i></div>
 <section class="game-arena ${phase==='hit'?'hit':''}">${mascot()}<div class="game-card"><span class="game-kicker">${item.kind==='word'?'WORD · 单词':'PHRASE · 短语'}</span><h1 class="game-word" lang="en-US">${esc(item.text)}</h1>${item.ipa?`<p class="game-ipa" lang="en-US">${esc(item.ipa)}</p>`:''}${item.speechNote?`<p class="small">${esc(item.speechNote)}</p>`:''}${item.text==='bedroom'?'<p class="game-audio-credit">本词真人示范：<a href="https://commons.wikimedia.org/wiki/File:En-us-bedroom.ogg" target="_blank" rel="noopener noreferrer">Dvortygirl / Wikimedia Commons 原音</a> · <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 3.0</a></p>':''}${training==='warmup'||translationShown?`<p class="game-translation">${esc(item.zh)}</p>`:btn('reveal-translation','查看中文（计入提示）',busy()?'disabled':'class="game-reveal"')}</div></section>
 <div class="game-actions">${btn('listen','▶ 听读',busy()?'disabled':'')}${btn('slow','慢读',busy()?'disabled':'')}${speaking?btn('stop-listen','停止示范'):''}</div><p id="game-speech-status" class="small" aria-live="polite">${esc(speech.snapshot().message||'')}</p>
 <div class="game-actions">${btn('record',phase==='permission'?'正在开启麦克风…':phase==='demo'?'先听示范…':phase==='buffer'?'准备好，轮到你读…':phase==='recording'?'🎙 请朗读 · 读完稍作停顿':phase==='encoding'?'正在处理录音…':phase==='assessing'?'正在评测…':phase==='hit'?'✓ 命中，准备下一词…':practice?'🎙 开始跟读录音':tries||hinted?'🎙 继续连续闯关':'🎙 开始连续闯关',`class="game-mic ${phase==='recording'?'recording':''}" ${busy()||speaking?'disabled':''}`)}${phase==='recording'?btn('finish-recording','我读完了','class="game-finish-recording"'):''}${blob?btn('replay','听听我刚才的录音',busy()?'disabled':''):''}</div>
 ${practice?`<p class="small">读完稍作停顿会自动结束；环境有噪声时，也可点“我读完了”。录音仅供本次回听，不上传、不评发音分数。</p><div class="game-actions">${btn('practiced','练完了，下一词 →',busy()?'disabled':'')}</div>`:'<p class="small">开始后会连续练习：读完自动评分，通过后自动换词；环境有噪声时可点“我读完了”。可随时暂停关闭麦克风。每次短录音最长 12 秒，会发送到腾讯云评测。</p>'}
 <div class="game-footer">${btn('skip','稍后再练',busy()?'disabled':'')}<span>${practice?`已练 ${results.filter(x=>x.outcome==='practice').length}`:`已命中 ${results.filter(x=>x.outcome==='pass').length}`} · ${tries?'本题已尝试 '+tries+' 次':'先听再读也可以'}</span></div>`;
}
function resultView(){
 const passed=results.filter(x=>x.outcome==='pass').length,first=results.filter(x=>x.outcome==='pass'&&!x.hinted&&x.tries===1).length;
 const stars=practice?0:passed>=queue.length*.7?(first>=queue.length*.8?3:2):1;
 const weak=results.filter(x=>!['pass','practice'].includes(x.outcome));
 const batchSources=new Set((data.sources||[]).filter(source=>source.batchId===data.batchId).map(source=>source.id));
 const batchUnits=new Set((data.units||[]).filter(unit=>unit.sources?.some(id=>batchSources.has(id))).map(unit=>unit.id));
 const scenario=[...(data.scenarios||[])].reverse().find(item=>item.unitIds?.some(id=>batchUnits.has(id)));
 const scenarioHref=scenario?`#scenarios/${encodeURIComponent(scenario.id)}`:'#scenarios/weekend-chat';
 return `<section class="game-panel game-result"><div class="game-kicker">这一局，给开口的自己一点掌声</div><h1>${practice?'跟读练习完成':'本轮闯关完成'}</h1>${practice?'<p>本轮是跟读试玩，未进行发音评分；跟读完成不代表已经掌握。</p>':`<div class="game-stars" aria-label="${stars} 星">${'★'.repeat(stars)}${'☆'.repeat(3-stars)}</div><p>${passed} / ${queue.length} 个目标发音通过 · ${stars>=2?'本轮发音表现达标；还要在情景中使用并按时复习。':'先练熟薄弱词，再来挑战。'}</p>`}<p>本轮${practice?'跟读 '+results.filter(x=>x.outcome==='practice').length:'通过 '+passed} 个目标，${weak.length} 个留待下次练习。</p>${weak.length?`<h2>留到下一轮</h2><ul class="game-weak-list">${weak.map(x=>`<li lang="en">${esc(deck.find(d=>d.id===x.id)?.text)}</li>`).join('')}</ul>`:'<p>下一次，试着少听一次示范。</p>'}${practice?'<p class="game-next-step">下一阶段：遮住中文，试着不听示范独立朗读。评分可用时，通过后才会计入发音进度。</p>':'<p class="game-next-step">下一阶段：在情景中用自己的话说一句，再按到期安排巩固。</p>'}<div class="game-actions">${practice?btn('independent-next',ready?'下一阶段 · 独立朗读闯关':'下一阶段 · 独立录音回听','class="game-start primary"'):''}<a class="button" href="${scenarioHref}">情景运用 · ${esc(scenario?.title||'开口练习')}</a>${btn('again','再练一局','class="game-start"')}${btn('home','返回游戏首页')}</div></section>`;
}
function paint(){if(!host?.isConnected)return;host.innerHTML=(storageOK?'':'<p class="game-banner warning">浏览器未能保存记录，请先导出备份。</p>')+(phase==='home'?home():phase==='result'?resultView():card())+`<p id="game-feedback" class="game-feedback ${phase==='hit'?'success':''}" role="status" aria-live="polite">${esc(status)}</p>`;}
// Clearing playback between targets must not release the prepared iOS microphone session.
function clearPlayback(){
 manualDemoKey=null;
 if(speechWait){const wait=speechWait;speechWait=null;wait.reject(cancelled());}
 speech.stop('');replay?.pause();replay=null;
 if(blobUrl)URL.revokeObjectURL(blobUrl);blobUrl=null;blob=null;
}
function cancelPending(){
 continuous=false;requestSerial++;abort?.abort();abort=null;
 clearTimeout(nextTimer);nextTimer=null;
 if(delayReject){const reject=delayReject;delayReject=null;reject(cancelled());}
 clearPlayback();recorder.release();
}
function persistRound(){
 if(!queue.length)return;
 // A confirmed hit is committed before its animation, so refresh cannot replay the score.
 const savedIndex=index+(passedCurrent?1:0);
 if(savedIndex>=queue.length){try{localStorage.removeItem(ROUND);}catch{storageOK=false;}return;}
 store(ROUND,{version:1,queue:queue.map(x=>x.id),index:savedIndex,results,roundId,practice,training,mode,group,hinted:passedCurrent?false:hinted,tries:passedCurrent?0:tries});
}
function delay(ms,serial){return new Promise((resolve,reject)=>{
 if(!valid(serial)){reject(cancelled());return;}
 delayReject=reject;nextTimer=setTimeout(()=>{nextTimer=null;delayReject=null;valid(serial)?resolve():reject(cancelled());},ms);
});}
function finishTarget(){
 index++;passedCurrent=false;hinted=false;translationShown=false;tries=0;manualDemoReady=null;status='';
 phase=index>=queue.length?'result':'question';persistRound();
}
function pauseFlow(message){
 if(passedCurrent)finishTarget();
 cancelPending();if(phase!=='home'&&phase!=='result')phase='question';
 status=message;persistRound();paint();
}
function startRound(isPractice=true){
 cancelPending();practice=isPractice;queue=C.makeQueue(deck,progress,{mode,batchId:data.batchId,group:group||groups[0],learnedGroups:prefs.learnedGroups,day:C.today(),limit:10,random:Math.random});
 if(!queue.length){phase='home';status=mode==='weak'?'已学范围内还没有薄弱词，可以先练一局。':mode==='due'?'当前没有待练词。请勾选已学范围，或从全部词库开始。':'这一组暂时没有可练内容。';paint();return;}
 index=0;results=[];roundId=crypto.randomUUID();hinted=false;translationShown=false;tries=0;passedCurrent=false;manualDemoReady=null;phase='question';status=practice?'听一遍，然后用自己的声音跟读。':'准备好后点一次开始。读完稍作停顿，就会自动评分和换词。';persistRound();paint();host?.scrollIntoView({block:'start'});
}
function restoreRound(r){
 if(!r||r.version!==1||!Array.isArray(r.queue)||!r.queue.length||r.queue.length>10||!Number.isInteger(r.index)||r.index<0||r.index>=r.queue.length)throw Error('上次练习无法恢复，学习记录仍保留。请开始新的一局。');
 const qs=r.queue.map(id=>deck.find(d=>d.id===id));if(qs.some(x=>!x))throw Error('词库已更新，请开始新的一局。已完成记录仍保留。');
 cancelPending();queue=qs;index=r.index;results=Array.isArray(r.results)?r.results.slice(0,index).map(x=>({id:String(x.id),outcome:['pass','practice','skip'].includes(x.outcome)?x.outcome:'skip',hinted:!!x.hinted,tries:Number(x.tries)||0})):[];
 practice=r.practice===true;training=r.training==='independent'?'independent':'warmup';mode=['batch','all','group','due','weak'].includes(r.mode)?r.mode:mode;if(groups.includes(r.group))group=r.group;roundId=String(r.roundId||crypto.randomUUID());hinted=!!r.hinted;translationShown=false;tries=Math.max(0,Number(r.tries)||0);passedCurrent=false;manualDemoReady=null;phase='question';status='已回到上次的位置。准备好后点开始，麦克风才会开启。';paint();host?.scrollIntoView({block:'start'});
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
 if(outcome==='pass'){if(!passedCurrent)return;}else{note(outcome);results.push({id:current().id,outcome,hinted,tries});}
 cancelPending();finishTarget();paint();host?.querySelector('h1')?.setAttribute('tabindex','-1');host?.querySelector('h1')?.focus({preventScroll:true});
}
function demo(serial,slow=false){
 if(!valid(serial))return Promise.reject(cancelled());
 hinted=true;manualDemoReady=null;phase='demo';status=slow?'再听一遍慢读，稍后自动轮到你。':'先听示范，读完后会自动轮到你。';persistRound();paint();
 return new Promise((resolve,reject)=>{
  speechWait={key:current().id,resolve,reject};
  speech.play({key:current().id,label:current().text,text:current().text,mode:slow?'slow':'normal'});
 });
}
function assertConnection(){if(!ready||!token||Date.now()>=expires)throw Error('评分连接已过期。本次没有上传录音，请保存退出后重新连接。');}
async function captureAudio(serial,keepSession){
 const item=current();clearPlayback();
 const capture=await recorder.start({autoStop:true,keepSession,kind:item.kind});
 if(!valid(serial))throw cancelled();
 phase='recording';status='轮到你了。正常朗读，读完稍作停顿，会自动结束录音。';paint();
 // Attach both handlers together: NO_SPEECH deliberately rejects result and exposes no Blob.
 const [audio,completion]=await Promise.all([capture.result,capture.completion]);
 if(!valid(serial))throw cancelled();
 if(completion.reason==='limit')throw Object.assign(Error('已到 12 秒，可能有环境声音或句子还没读完。这次未上传，也不算读错；安静后再继续。'),{code:'RECORDING_LIMIT'});
 if(completion.reason==='cancelled')throw cancelled();
 if(completion.speechDetected===false||completion.reason==='no_speech')throw Object.assign(Error('这次没有听到清楚的朗读，不上传、不算读错。准备好再继续。'),{code:'NO_SPEECH'});
 blob=audio;blobUrl=URL.createObjectURL(audio);phase='encoding';status='正在整理这次录音…';paint();
 const wav=await recorder.encode(audio);if(!valid(serial))throw cancelled();
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
 if(e.code==='DEMO_UNAVAILABLE')return '示范声音未能播放，练习已暂停。请亲自点「听读」或「慢读」，听完再点继续。';
 if(e.name==='AbortError')return '评分等待较久，已暂停。这次不算读错，也不会自动重试上传；准备好再继续。';
 return e.message||'这次未能完成评测，已暂停，没有记为发音错误。';
}
async function record(){
 if(busy()||!current()||document.hidden)return;
 if(!practice){try{assertConnection();}catch(e){pauseFlow(errorMessage(e));return;}}
 clearPlayback();abort?.abort();const serial=++requestSerial;continuous=!practice;
 phase='permission';status='请允许麦克风。每次朗读后稍作停顿，会自动结束录音。';
 // Keep this call in the click stack: AudioContext.resume must precede await on iOS.
 let prepared;try{prepared=recorder.prepare();}catch(e){pauseFlow(errorMessage(e));return;}paint();
 try{
  await prepared;if(!valid(serial))return;
  if(practice){await captureAudio(serial,false);if(!valid(serial))return;phase='question';status='录好了。听听自己的声音，练完后继续下一词。本轮不评发音分数。';paint();return;}
  let burstAttempts=0,retrying=false;
  while(valid(serial)&&continuous&&current()){
   assertConnection();
   const demonstrated=manualDemoReady===current().id;manualDemoReady=null;
   if(retrying||(training==='warmup'&&!demonstrated))await demo(serial,retrying);
   if(!valid(serial))return;
   phase='buffer';status='轮到你了，准备开口…';paint();await delay(650,serial);
   const wav=await captureAudio(serial,true);if(!valid(serial))return;
   const result=await assess(wav,serial);if(!valid(serial))return;
   if(result.status==='uncertain'){pauseFlow(result.feedback||'这次评分未能确认，已暂停，没有记为发音错误。');return;}
   tries++;burstAttempts++;note(result.status);
   const score=typeof result.score==='number'&&Number.isFinite(result.score)&&result.score>=0&&result.score<=100?`本次评分 ${Math.round(result.score)}/100 · `:'';
   status=score+(result.feedback||(result.status==='pass'?'读得清楚，命中！':'再练一次，会更清楚。'));
   if(result.status==='pass'){
    passedCurrent=true;results.push({id:current().id,outcome:'pass',hinted,tries});phase='hit';persistRound();paint();
    await delay(1300,serial);if(!valid(serial))return;
    clearPlayback();finishTarget();paint();
    if(phase==='result'){cancelPending();paint();return;}
    burstAttempts=0;retrying=false;
   }else{
    persistRound();
    if(burstAttempts>=3){pauseFlow(status+' 本词已连续练习 3 次，先休息一下。可以继续或稍后再练。');return;}
    phase='buffer';paint();await delay(1400,serial);retrying=true;
   }
  }
 }catch(e){if(!valid(serial))return;pauseFlow(errorMessage(e));}
}
function connectView(savedRound=null){
 if(!ready)return;
 cancelPending();phase='home';paint();const panel=document.createElement('section');panel.className='game-panel';panel.innerHTML=`<h2>连接发音评分</h2><p>${esc(config.cloudNotice||'短录音将发送到腾讯云做本次评测。')}</p><p class="small">使用你已解锁的英语栏目自动连接，无需再输入评分口令。你点击开始连续闯关后，每题读完会自动评分并进入下一题；暂停或切到后台立即关闭麦克风。服务异常不计为发音错误。</p><form id="game-connect"><label><input type="checkbox" id="game-consent" required> 同意将本次练习的短录音发送给腾讯云评分</label><button class="game-start" type="submit">同意并连接评分</button><p id="game-connect-status" role="status"></p></form>`;
 host.prepend(panel);panel.querySelector('form').addEventListener('submit',async e=>{
 e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;const serial=++requestSerial;abort=new AbortController();const timeout=setTimeout(()=>abort?.abort(),8000);
 try{const password=await siteCredential();if(serial!==requestSerial)return;const result=await jsonFetch('/session',{method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,body:JSON.stringify({password})});if(serial!==requestSerial)return;
 if(typeof result.token!=='string'||!Number.isFinite(Date.parse(result.expiresAt)))throw Error('评分服务返回了无效连接。');token=result.token;expires=Date.parse(result.expiresAt);if(savedRound)restoreRound(savedRound);else startRound(false);
 }catch(err){if(serial!==requestSerial)return;panel.querySelector('#game-connect-status').textContent=err.name==='AbortError'?'连接超时，请稍后再试。':err.status===401?'网站解锁状态与评分服务尚未同步，请稍后再试。':err.message;button.disabled=false;}finally{clearTimeout(timeout);}
 });panel.querySelector('#game-consent').focus();
}
function handle(e){
 const b=e.target.closest('[data-game]');if(!b||b.disabled)return;
 switch(b.dataset.game){
 case'mode':mode=b.dataset.mode;status='';paint();break;
 case'latest':mode='batch';training='warmup';startRound(true);break;
 case'start':startRound(true);break;
 case'independent-next':training='independent';if(ready)connectView();else startRound(true);break;
 case'challenge':connectView();break;
 case'resume':resume();break;
 case'reveal-translation':if(!busy()&&current()){hinted=true;translationShown=true;status='已查看中文，本题会记为有提示练习。';persistRound();paint();}break;
 case'listen':case'slow':if(!busy()&&current()){hinted=true;manualDemoKey=current().id;manualDemoReady=null;replay?.pause();speech.play({key:current().id,label:current().text,text:current().text,mode:b.dataset.game==='slow'?'slow':'normal'});paint();}break;
 case'stop-listen':if(continuous)pauseFlow('练习已暂停，麦克风已关闭。准备好后继续。');else{manualDemoKey=null;speech.stop('');paint();}break;
 case'record':record();break;
 case'finish-recording':if(phase==='recording')recorder.stop();break;
 case'pause':pauseFlow('练习已暂停，麦克风已关闭。准备好后继续；已通过的成绩已保存。');break;
 case'replay':if(blobUrl&&!busy()){speech.stop('');replay?.pause();replay=new Audio(blobUrl);replay.play().catch(()=>{status='回放暂时不可用，请再点一次。';paint();});}break;
 case'practiced':if(practice&&!busy())advance('practice');break;
 case'skip':if(!busy())advance('skip');break;
 case'leave':pauseFlow('已暂停，已完成的学习记录已保存。');phase='home';paint();break;
 case'home':cancelPending();phase='home';status='';paint();break;
 case'again':if(!practice&&(!token||Date.now()>=expires)){phase='home';paint();connectView();}else startRound(practice);break;
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
function unmount(){if(!initialized)return;if(passedCurrent)finishTarget();if(phase!=='home'&&phase!=='result')persistRound();cancelPending();host=null;phase='home';token='';expires=0;}
root.addEventListener('pagehide',unmount);
root.addEventListener('pageshow',e=>{if(e.persisted&&initialized&&document.getElementById('english-game')){host=document.getElementById('english-game');phase='home';status='欢迎回来，已完成的记录已保留。';paint();}});
root.document.addEventListener('visibilitychange',()=>{if(document.hidden&&initialized){pauseFlow('练习已暂停，麦克风已关闭。回到页面后，请亲自点继续。');}});
root.EnglishGame={view,mount,unmount};
})(globalThis);
