// AI assessment: classifier (mock of the Claude vision call), sample photos, and the shared result card
const AIL=()=>lang=="hi"?{h:"AI आकलन",bl:"चेहरे धुंधले ✓",ty:"समस्या",sv:"गंभीरता",cf:"भरोसा",wh:"कारण",adv:"यह अधिकारी के लिए सलाह है। अधिकारी स्कोर बदल सकता है।",vo:"आवाज़ का लिखित रूप",tr:"अंग्रेज़ी अनुवाद"}:{h:"AI assessment",bl:"Faces blurred ✓",ty:"Problem",sv:"Severity",cf:"Confidence",wh:"Reason",adv:"This is advice to the officer. An officer can change the score.",vo:"Voice note transcript",tr:"English translation"};
const REASON={overflow:["Sewage is pooling on the lane near the tank cover; people and children can come into contact.","Wet stain and foul liquid around the inspection cover; the tank looks full.","Liquid seeping along a wall; cause not clear from the photo."],dumping:["A tanker is discharging into an open drain, not at a plant.","Dark liquid running from a hose into a canal edge."],manual:["A worker is inside or at the mouth of a tank with no gear. This is an emergency.","Person bending into a tank opening with no harness or mask."]};
function classify(type,hasPhoto){const sev=type=="manual"||type=="dumping"?3:hasPhoto?3:2,conf=hasPhoto?+(.84+Math.random()*.1).toFixed(2):.7,list=REASON[type];
return{sev,conf,why:hasPhoto?list[0]:"Based on the text only; an officer will confirm."}}
function addReport(type,x,y,hasPhoto,extra){const c=classify(type,hasPhoto);const r={id:"R-"+(21+reports.length),type,x,y,age:0,...c,...(extra||{})};reports.push(r);return r}
// Sample photos drawn as small SVG scenes, so the demo needs no real upload
function samplePhoto(type){
const sky='<rect width="320" height="200" fill="#bfe3ef"/><rect y="130" width="320" height="70" fill="#9a8f7c"/><rect y="150" width="320" height="50" fill="#85796a"/>';
const house='<rect x="10" y="60" width="90" height="80" fill="#e8d9c0"/><path d="M0 62L55 20 110 62z" fill="#b5654a"/><rect x="40" y="95" width="26" height="45" fill="#6b4b36"/>';
let g="";
if(type=="dumping")g=`${sky}${house}<rect x="150" y="85" width="120" height="50" rx="22" fill="#4f6f7a"/><rect x="262" y="100" width="40" height="35" fill="#34505b"/><circle cx="180" cy="140" r="11" fill="#222"/><circle cx="276" cy="140" r="11" fill="#222"/><path d="M170 135 Q160 165 120 178 L300 190 L190 150z" fill="#5a4630" opacity=".85"/><rect x="95" y="172" width="70" height="12" rx="6" fill="#2b241a"/>`;
else if(type=="manual")g=`${sky}${house}<ellipse cx="215" cy="150" rx="55" ry="16" fill="#555"/><ellipse cx="215" cy="146" rx="42" ry="10" fill="#111"/><circle cx="215" cy="120" r="11" fill="#c59470"/><rect x="204" y="128" width="22" height="26" rx="6" fill="#8aa2b8"/><rect x="190" y="90" width="50" height="14" fill="none"/>`;
else g=`${sky}${house}<ellipse cx="200" cy="162" rx="105" ry="22" fill="#6a5430" opacity=".9"/><ellipse cx="190" cy="158" rx="60" ry="11" fill="#7d6638" opacity=".9"/><ellipse cx="150" cy="138" rx="26" ry="8" fill="#555"/><rect x="132" y="128" width="36" height="10" rx="3" fill="#777"/><path d="M110 150 Q60 165 20 190" stroke="#6a5430" stroke-width="9" fill="none" opacity=".8"/>`;
return "data:image/svg+xml;utf8,"+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200">${g}</svg>`)}
const VOICE={hi:"टैंक का ढक्कन टूट गया है और गली में गंदा पानी बह रहा है।",en:"The tank cover is broken and dirty water is flowing into the lane."};
function sevBar(s){return `<div class="sevb" aria-label="Severity ${s} of 3">${[1,2,3].map(i=>`<i class="${i<=s?"on s"+s:""}"></i>`).join("")}<b>${s}/3</b></div>`}
function confBar(c){const p=Math.round(c*100);return `<div class="cfb"><u><i style="width:${p}%"></i></u><b>${p}%</b></div>`}
function aiCard(r,o){o=o||{};const L=AIL();
return `<div class="ai"><div class="aih"><span class="aib">✦ ${L.h}</span><span class="tag t-g">${L.bl}</span></div>
${r.img?`<img class="aiimg" src="${r.img}" alt="Photo submitted with the report">`:""}
${r.vh?`<div class="aivo"><small>🎤 ${L.vo}</small><p lang="hi">${esc(r.vh)}</p><small>${L.tr}</small><p>${esc(r.ve)}</p></div>`:""}
<div class="aig"><div><small>${L.ty}</small><b>${typeName[r.type]}</b></div><div><small>${L.sv}</small>${sevBar(r.sev)}</div><div><small>${L.cf}</small>${confBar(r.conf)}</div></div>
<p class="aiw"><small>${L.wh}</small><br>${esc(r.why)}</p>${o.noAdv?"":`<p class="aia">${L.adv}</p>`}</div>`}
// Staged "AI is reading" checklist, used by the report page and the chat bot
const AISTEPS=["Checking the photo for faces and house interiors","Reading the scene with Claude vision","Matching the location to Ward 12","Scoring severity 1 to 3"];
function aiSteps(n){return `<div class="aist">${AISTEPS.map((s,i)=>`<div class="${i<n?"d":i==n?"c":""}"><i></i>${s}</div>`).join("")}</div>`}

reports.forEach(r=>{if(["R-21","R-22","R-23","R-26"].includes(r.id))r.img=samplePhoto(r.type)});
