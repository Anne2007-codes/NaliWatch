// Guided demo: walks the whole loop (report -> AI -> map -> operator -> driver -> plant -> flag -> public) in about 3 minutes.
// Each step navigates to a screen and performs the action through the same functions the buttons use.
let D={i:-1,run:0,auto:0,tr:null,rep:null,flag:null,ran:0};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(f,max){const t0=Date.now();while(!f()&&Date.now()-t0<(max||8000))await wait(120)}
const DEMO=[
{t:"A resident reports on WhatsApp",h:"निवासी व्हाट्सऐप पर रिपोर्ट करता है",d:"A resident sends a photo of an overflowing tank. No app to install, and the location comes from the phone.",dh:"निवासी ओवरफ़्लो टैंक की फ़ोटो भेजता है। कोई ऐप नहीं चाहिए।",
 run:async()=>{go("bot");await wait(700);bs("overflow");await waitFor(()=>!bq,9000);D.rep=reports[reports.length-1]}},
{t:"AI reads the photo and scores it",h:"AI फ़ोटो पढ़कर स्कोर देता है",d:"Faces are blurred, the scene is read, and severity 1 to 3 comes back with a reason and a confidence. It is advice: an officer can always change it.",dh:"चेहरे धुंधले होते हैं, गंभीरता 1 से 3 और कारण मिलता है। अधिकारी इसे बदल सकता है।",
 run:async()=>{await wait(1600)}},
{t:"The report lands on the live ward map",h:"रिपोर्ट लाइव वार्ड मैप पर आती है",d:"The new report joins an existing risk zone. Overflow reports plus 9 sickness cases from ASHA workers in the same lane is an early warning.",dh:"नई रिपोर्ट जोखिम क्षेत्र में जुड़ती है। उसी गली में 9 बीमारी के मामले एक शुरुआती चेतावनी हैं।",
 run:async()=>{seeOnMap(D.rep.id);await wait(2800)}},
{t:"An operator accepts jobs and plans one trip",h:"ऑपरेटर काम स्वीकार कर एक ट्रिप बनाता है",d:"Nearby overdue tanks are batched into one tanker trip, most urgent first, inside the tanker's capacity.",dh:"पास के लेट टैंक एक ट्रिप में जुड़ते हैं, सबसे ज़रूरी पहले।",
 run:async()=>{go("operator");await wait(900);acc("T-101");await wait(700);acc("T-109");await wait(700);mk();D.tr=trips[trips.length-1];await wait(1200)}},
{t:"The driver confirms every pick-up with an OTP",h:"ड्राइवर हर पिक-अप OTP से कन्फ़र्म करता है",d:"The household gives a one-time code at the tank. That is the proof the pump-out happened at that address.",dh:"घर वाले टैंक पर एक OTP देते हैं। यही सबूत है कि पंप-आउट उसी पते पर हुआ।",
 run:async()=>{dv=D.tr.driver;go("driver");await wait(900);for(let i=0;i<D.tr.stops.length;i++){const e=$("#o"+D.tr.id+i);if(e)e.value="1234";otpc(D.tr.id,i);await wait(800)}stt(D.tr.id,"enroute");await wait(900)}},
{t:"The tanker drives to the plant, GPS trail live",h:"टैंकर प्लांट की ओर, GPS ट्रेल लाइव",d:"The officer watches the trail on the map. A GPS gap or a detour is checked by a person before anyone is blamed.",dh:"अधिकारी मैप पर ट्रेल देखता है। GPS गैप की जाँच इंसान करता है।",
 run:async()=>{go("officer");await wait(900);await new Promise(res=>playTrip(D.tr,()=>{D.tr.st="arrived";aud(D.tr.id+" arrived at plant");draw();res()},8500));await wait(500)}},
{t:"The plant confirms the volume: verified drop",h:"प्लांट मात्रा की पुष्टि करता है: सत्यापित ड्रॉप",d:"Plant staff enter the litres received. Within the municipality's tolerance, the trip closes with a verified-drop receipt.",dh:"प्लांट स्टाफ मात्रा दर्ज करता है। सीमा के भीतर हो तो ट्रिप सत्यापित रसीद के साथ बंद होती है।",
 run:async()=>{go("plant");await wait(900);const e=$("#r"+D.tr.id);if(e)e.value=pumped(D.tr)-9;await wait(1100);conf(D.tr.id);await wait(3800)}},
{t:"A skipped plant becomes a flag",h:"छूटा हुआ प्लांट फ़्लैग बन जाता है",d:"If a tanker never reaches the plant, or the volume does not match, the trip cannot close. It goes to the ward officer as a flag.",dh:"अगर टैंकर प्लांट नहीं पहुँचता तो ट्रिप बंद नहीं होती और फ़्लैग बनता है।",
 run:async()=>{closeReceipt();go("operator");await wait(900);sim(0);await waitFor(()=>!LT&&trips[trips.length-1].st=="flagged",20000);await wait(1800);closeReceipt();D.flag=flags[flags.length-1]}},
{t:"A person reviews the flag. Nobody is penalised automatically",h:"फ़्लैग की समीक्षा इंसान करता है",d:"The officer sees the route, volumes and the GPS gap, then clears it, asks the operator to explain, or escalates.",dh:"अधिकारी रूट, मात्रा और GPS गैप देखकर फ़ैसला करता है।",
 run:async()=>{go("flags");await wait(900);fs=D.flag.id;draw();await wait(2600);dec(D.flag.id,"Asked operator to explain");await wait(1200)}},
{t:"Everyone sees ward-level proof, never names",h:"सब को वार्ड-स्तर का सबूत, नाम कभी नहीं",d:"The public page shows tanks emptied on schedule, confirmed drops and hotspots. No names, phone numbers or exact addresses.",dh:"सार्वजनिक पेज पर वार्ड-स्तर के आँकड़े हैं। नाम, फ़ोन या पते नहीं।",
 run:async()=>{go("pub");await wait(1500)}}];
function startDemo(){if(D.ran){location.href=location.pathname+"?demo=1#bot";return}
D.i=-1;D.run=0;D.auto=0;document.body.classList.add("demo");demoNext()}
async function demoNext(){if(D.run)return;if(D.i>=DEMO.length-1){D.i=DEMO.length;D.auto=0;D.ran=1;demoUI();return}
D.i++;D.run=1;D.ran=1;closeReceipt();demoUI();try{await DEMO[D.i].run()}catch(e){console.error(e)}D.run=0;demoUI();
if(D.auto){await wait(2200);if(D.auto&&!D.run)demoNext()}}
function demoAuto(){D.auto=!D.auto;demoUI();if(D.auto&&!D.run)demoNext()}
function demoExit(){D.auto=0;D.i=-1;document.body.classList.remove("demo");demoUI();closeReceipt()}
function demoUI(){const el=$("#demo");if(!el)return;if(D.i<0){el.innerHTML="";return}const hi=lang=="hi",n=DEMO.length;
if(D.i>=n){el.innerHTML=`<div class="dm"><div class="dmh"><b>${hi?"गाइडेड डेमो":"Guided demo"}</b><button onclick="demoExit()" aria-label="Close demo">×</button></div><h3>${hi?"यही पूरा लूप है":"That is the full loop"}</h3><p>${hi?"घर से सत्यापित ड्रॉप तक, हर लोड का रिकॉर्ड।":"Household to verified drop, with a record at every step. Every flag is reviewed by a person."}</p><div class="row"><button class="btn g" onclick="startDemo()">↻ ${hi?"फिर से चलाएँ":"Run again"}</button><button class="btn" onclick="demoExit()">${hi?"बंद करें":"Close"}</button></div></div>`;return}
const s=DEMO[D.i];
el.innerHTML=`<div class="dm" role="region" aria-label="Guided demo"><div class="dmh"><b>${hi?"गाइडेड डेमो":"Guided demo"}</b><span>${hi?"चरण":"Step"} ${D.i+1}/${n}</span><button onclick="demoExit()" aria-label="Close demo">×</button></div><div class="dmp">${DEMO.map((_,i)=>`<i class="${i<D.i?"d":i==D.i?"c":""}"></i>`).join("")}</div><h3>${hi?s.h:s.t}</h3><p>${hi?s.dh:s.d}</p><div class="row"><button class="btn g" onclick="demoNext()" ${D.run?"disabled":""}>${D.run?(hi?"चल रहा है…":"Playing…"):D.i==n-1?(hi?"समाप्त":"Finish"):(hi?"अगला ▶":"Next ▶")}</button><button class="btn" onclick="demoAuto()">${D.auto?"⏸ "+(hi?"रोकें":"Pause"):"▶ "+(hi?"ऑटो-प्ले":"Auto-play")}</button></div></div>`}
addEventListener("load",()=>{if(/[?&]demo=1/.test(location.search)){history.replaceState(null,"",location.pathname+location.hash);setTimeout(startDemo,500)}});
