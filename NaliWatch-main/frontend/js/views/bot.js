// WhatsApp-style chat bot simulator: photo, voice and text reports, with the AI result as a bot reply
let chat=[],bq=0;
const BG={w:"Namaste! नमस्ते! Send a photo, a voice note or a few words and I will log a report. Your location is taken from your phone."};
function bubble(m){
if(m.typing)return `<div class="m bot typ"><i></i><i></i><i></i></div>`;
if(m.img)return `<div class="m me pic"><img src="${m.img}" alt="Photo sent in chat"><small>${m.t||""}</small></div>`;
if(m.vo)return `<div class="m me vo"><span class="wf">${"<i></i>".repeat(16)}</span> 0:07<small>${m.t||""}</small></div>`;
if(m.ai)return `<div class="m bot wide">${aiCard(m.ai,{noAdv:1})}<button class="btn g" onclick="seeOnMap('${m.ai.id}')">See ${m.ai.id} on the map</button></div>`;
return `<div class="m ${m.w}">${esc(m.t)}${m.tick?'<span class="tk">✓✓</span>':""}</div>`}
function bot(){if(!chat.length)chat=[{w:"bot",t:BG.w}];
return `<h1>WhatsApp-style chat</h1><div class="split"><div class="card"><div class="wah"><b>NaliWatch</b><small>${bq?"typing…":"online"}</small></div><div class="chat" id="ch">${chat.map(bubble).join("")}</div>
<p class="row"><button class="chip pr" onclick="bs('overflow')">📷 Overflow photo</button><button class="chip" onclick="bs('dumping')">📷 Dumping photo</button><button class="chip" onclick="bs('manual')">📷 Manual cleaning</button><button class="chip" onclick="bs('voice')">🎤 Voice note</button></p>
<div class="row"><input id="bt" placeholder="Type a message" style="flex:1" onkeydown="if(event.key=='Enter')bs('t')"><button class="btn g" onclick="bs('t')">Send</button></div></div>
<div class="card y"><h2>How it works</h2><p>Send a photo, a voice note or text. The bot reads it with AI, replies with the severity, and the report appears on the officer map.</p><ol class="hw"><li>Resident sends a photo</li><li>AI blurs faces and scores severity 1 to 3</li><li>Officer sees it on the map and dispatches</li></ol><p class="aia">Tip: tap “Overflow photo” to see the full loop.</p></div></div>`}
function seq(steps){bq=1;let t=0;steps.forEach((s,i)=>{t+=s[0];setTimeout(()=>{s[1]();if(i==steps.length-1)bq=0;draw();const c=$("#ch");if(c)c.scrollTop=1e5},t)})}
const unTyp=()=>{chat=chat.filter(m=>!m.typing)};
function bs(k){if(bq)return;const tx=$("#bt")?$("#bt").value.trim():"";let type="overflow",ex={},me;
if(k=="t"){if(!tx)return;me={w:"me",t:tx,tick:1};type=/dump|tanker|drain/i.test(tx)?"dumping":/inside|enter|manual|worker|hand/i.test(tx)?"manual":"overflow"}
else if(k=="voice"){me={w:"me",vo:1,t:"Hindi"};ex={vh:VOICE.hi,ve:VOICE.en}}
else{type=k;me={w:"me",img:samplePhoto(k),t:"📍 Location attached"};ex={img:me.img}}
chat.push(me);chat.push({typing:1});draw();const c0=$("#ch");if(c0)c0.scrollTop=1e5;
let r;
seq([[900,()=>{unTyp();if(k=="voice")chat.push({w:"bot",t:"Heard it. Transcript: “"+VOICE.hi+"” — “"+VOICE.en+"”"});else chat.push({w:"bot",t:"Got it. Reading your report… 🔍"});chat.push({typing:1})}],
[1300,()=>{unTyp();r=addReport(type,105+Math.random()*50,105+Math.random()*50,k!="t",ex);aud(r.id+" reported via chat bot");chat.push({w:"bot",ai:r})}],
[600,()=>{chat.push({w:"bot",t:r.type=="manual"?`Report ${r.id} logged as an EMERGENCY. A named responder, Rakesh Kumar, is being called now on +91 98XXX 12345.`:`Report ${r.id} logged. A ward officer will review it and send a certified operator.`})}]]);
if($("#bt"))$("#bt").value=""}
