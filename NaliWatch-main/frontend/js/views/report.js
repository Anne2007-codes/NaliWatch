// Reporter: icon-card problem type, photo (real or sample), voice note, location; AI result shown live
let rp={type:"overflow",photo:null,sample:0,voice:0,note:"",loc:"Use my location",stage:-1,result:null};
const RT=[["overflow","Overflow","Tank or drain overflowing","s5"],["dumping","Dumping","Tanker dumping sewage","operator"],["manual","Manual cleaning","Person cleaning a tank by hand","asha"]];
const RTH={overflow:["ओवरफ़्लो","टैंक या नाली उफन रही है"],dumping:["डंपिंग","टैंकर गंदगी फेंक रहा है"],manual:["हाथ से सफ़ाई","कोई टैंक में हाथ से सफ़ाई कर रहा है"]};
const RF=()=>lang=="hi"?{w:"क्या हो रहा है?",p:"फ़ोटो (चेहरे या घर के अंदर की तस्वीर नहीं)",pt:"फ़ोटो जोड़ने के लिए छुएँ",ps:"नमूना फ़ोटो लें",v:"आवाज़ (हिंदी या अंग्रेज़ी)",vr:"आवाज़ रिकॉर्ड करें",vs:"रोकें",vd:"आवाज़ सहेजी ✓",l:"कहाँ?",n:"नोट",nx:"आगे क्या होता है",nxp:"AI आपकी फ़ोटो और नोट पढ़ता है, समस्या को 1 से 3 में आँकता है, और वार्ड अधिकारी समीक्षा करता है। आपका नाम ऑपरेटर से छिपा रहता है।"}:{w:"What is happening?",p:"Photo (no faces or house interiors)",pt:"Tap to add a photo",ps:"Use a sample photo",v:"Voice note (Hindi or English)",vr:"Record voice note",vs:"Stop recording",vd:"Voice note saved ✓",l:"Where?",n:"Note",nx:"What happens next",nxp:"AI reads your photo and note, scores the problem 1 to 3, and a ward officer reviews it. Your name is hidden from operators."};
function report(){const L=RF();
return `<h1>Report a problem</h1><div class="split"><div class="card"><label>${L.w}</label><div class="tpc">${RT.map(r=>`<button class="${rp.type==r[0]?"on":""}" onclick="rpT('${r[0]}')" aria-pressed="${rp.type==r[0]}"><i>${ic(r[3])}</i><b>${lang=="hi"?RTH[r[0]][0]:r[1]}</b><span>${lang=="hi"?RTH[r[0]][1]:r[2]}</span></button>`).join("")}</div>
<label>${L.p}</label><div class="drop ${rp.photo?"has":""}" ondragover="event.preventDefault()" ondrop="event.preventDefault();rpF(event.dataTransfer.files[0])">${rp.photo?`<img src="${rp.photo}" alt="Selected photo preview"><button class="chip" onclick="rpX()">Remove</button>`:`<label for="ph" class="dz"><i>${ic("report")}</i>${L.pt}<small>or drop an image here</small></label><input id="ph" type="file" accept="image/*" hidden onchange="rpF(this.files[0])">`}</div>${rp.photo?"":`<p><button class="chip" onclick="rpS()">${L.ps}</button></p>`}
<label>${L.v}</label><button class="btn y" onclick="vn()">${rp.voice==1?"● "+L.vs:rp.voice==2?L.vd:L.vr}</button>${rp.voice==2?`<div class="aivo"><small>🎤 Transcript (Hindi)</small><p lang="hi">${VOICE.hi}</p><small>English translation</small><p>${VOICE.en}</p></div>`:""}
<label for="lo">${L.l}</label><select id="lo" onchange="rp.loc=this.value">${["Use my location",...Object.keys(areas)].map(a=>`<option ${a==rp.loc?"selected":""}>${a}</option>`).join("")}</select>
<label for="nt">${L.n}</label><textarea id="nt" rows="2" oninput="rp.note=this.value">${esc(rp.note)}</textarea><p></p><button class="btn g" onclick="sendR()" ${rp.stage>=0?"disabled":""}>${t("send")}</button></div>
<div class="card y" id="res">${rpRes(L)}</div></div>`}
function rpRes(L){
if(rp.stage>=0)return `<h2>✦ AI is reading your report</h2>${aiSteps(rp.stage)}`;
const r=rp.result;if(!r)return `<h2>${L.nx}</h2><p>${L.nxp}</p><p class="aia">Try it: pick a type, tap “${L.ps}” and send.</p>`;
return `<h2>${r.id} received</h2>${aiCard(r)}${r.type=="manual"?`<p class="emg"><b>Emergency:</b> a named human responder is being called now.</p>`:`<p>An officer will review it and dispatch a certified operator.</p>`}<button class="btn g" onclick="seeOnMap('${r.id}')">See it on the map</button>`}
function rpT(k){rp.type=k;if(rp.sample)rp.photo=samplePhoto(k);draw()}
function rpS(){rp.photo=samplePhoto(rp.type);rp.sample=1;draw()}
function rpX(){rp.photo=null;rp.sample=0;draw()}
function rpF(f){if(!f)return;rp.file=f;const fr=new FileReader();fr.onload=()=>{rp.photo=fr.result;rp.sample=0;draw()};fr.readAsDataURL(f)}
function vn(){if(rp.voice==1){rp.voice=2}else rp.voice=1;draw()}
function seeOnMap(id){go("officer");setTimeout(()=>{sel=id;draw();if(window.mapFocus)mapFocus(id)},90)}
function sendR(){if(rp.stage>=0)return;if(!rp.photo&&rp.voice!=2&&!rp.note.trim())return say("Add a photo, a voice note or a few words first");
rp.stage=0;rp.result=null;draw();const iv=setInterval(()=>{rp.stage++;if(rp.stage>=AISTEPS.length){clearInterval(iv);finishR()}else draw()},620)}
async function finishR(){const l=rp.loc,p=areas[l]||[105+Math.random()*50,105+Math.random()*50],x=p[0]+(areas[l]?0:0),ex={};
if(rp.photo)ex.img=rp.photo;if(rp.voice==2){ex.vh=VOICE.hi;ex.ve=VOICE.en}
if(token){try{const ll=ll2(p[0],p[1]),fd=new FormData();fd.append("lat",String(ll[1]));fd.append("lng",String(ll[0]));if(rp.note)fd.append("text",rp.note);fd.append("claimed_type",rp.type==="manual"?"manual_cleaning":rp.type);if(rp.file)fd.append("photo",rp.file,rp.file.name||"photo.jpg");const r=await api.postForm("/reports",fd);const mapped=mapType(r.type);rp.result={id:"R-"+r.id,rawId:r.id,type:mapped,sev:r.severity,conf:r.confidence,why:r.summary||r.ai_reason||"",x,y:p[1],...ex};if(mapped==="manual")rp.result.emg=1;rp.stage=-1;await loadLive();draw();return}catch(e){rp.stage=-1;draw();return say(e.message||"Could not submit report")}}
rp.result=addReport(rp.type,x,p[1],!!rp.photo,ex);rp.stage=-1;aud(rp.result.id+" reported and scored by AI");
if(rp.type=="manual")rp.result.emg=1;draw()}