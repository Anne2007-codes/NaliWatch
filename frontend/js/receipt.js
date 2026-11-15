// Verified-drop receipt: the proof a trip ended at an authorized plant (QR + timeline)
function qrSvg(seed){let h=0;for(const c of seed)h=(h*31+c.charCodeAt(0))>>>0;const n=21,cell=6,rnd=()=>(h=(h*1664525+1013904223)>>>0)/4294967296;let g="";
const fin=(x,y)=>`<rect x="${x*cell}" y="${y*cell}" width="${7*cell}" height="${7*cell}" fill="#06222f"/><rect x="${(x+1)*cell}" y="${(y+1)*cell}" width="${5*cell}" height="${5*cell}" fill="#fff"/><rect x="${(x+2)*cell}" y="${(y+2)*cell}" width="${3*cell}" height="${3*cell}" fill="#06222f"/>`;
const inF=(i,j)=>(i<8&&j<8)||(i>n-9&&j<8)||(i<8&&j>n-9);
for(let j=0;j<n;j++)for(let i=0;i<n;i++)if(!inF(i,j)&&rnd()>.52)g+=`<rect x="${i*cell}" y="${j*cell}" width="${cell}" height="${cell}" fill="#06222f"/>`;
return `<svg viewBox="0 0 ${n*cell} ${n*cell}" width="112" height="112" role="img" aria-label="QR code to verify trip ${seed}"><rect width="${n*cell}" height="${n*cell}" fill="#fff"/>${g}${fin(0,0)}${fin(n-7,0)}${fin(0,n-7)}</svg>`}
function showReceipt(tr){const el=$("#rcpt");if(!el)return;const bad=tr.st=="flagged",pm=pumped(tr),rc=tr.recv,diff=rc==null?null:Math.abs(rc-pm)*100/pm,ok=!bad&&rc!=null;
const clk=m=>new Date(Date.now()-m*60000).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
const S=[[`Pick-ups confirmed with household OTP`,tr.stops.map(s=>`${s.k} · ${s.vol} L · ${s.d?"OTP ✓":"pending"}`).join("<br>"),clk(58),tr.stops.every(s=>s.d)?1:0],
[`GPS trail recorded`,tr.gap?`${tr.gap} min gap detected. Reviewed by an officer first.`:`Complete trail, no gaps`,clk(41),tr.gap?2:1],
[`Entered plant geofence`,rc==null?`No plant arrival recorded`:`Hisar STP 1 · inside the 150 m geofence`,clk(14),rc==null?0:1],
[`Volume matched at plant`,rc==null?`No plant confirmation`:`${pm} L pumped · ${rc} L received · difference ${diff.toFixed(1)}% (tolerance ${tol}%)`,clk(9),rc==null?0:diff<=tol?1:0]];
const verdict=ok?"VERIFIED DROP":"FLAGGED FOR REVIEW";
el.innerHTML=`<div class="ov" onclick="if(event.target==this)closeReceipt()"><div class="rcp ${ok?"ok":"bad"}" role="dialog" aria-modal="true" aria-label="Trip receipt"><button class="x" onclick="closeReceipt()" aria-label="Close">×</button>
<div class="rch"><div><small>NaliWatch trip ticket</small><h2>${tr.id}</h2><p>${tr.driver} · ${tr.veh} · ${new Date().toLocaleDateString([],{day:"numeric",month:"short",year:"numeric"})}</p></div>${qrSvg(tr.id)}</div>
<div class="rcv">${ok?"✓":"!"} ${verdict}</div>
<ol class="rcl">${S.map(s=>`<li class="${s[3]==1?"d":s[3]==2?"w":"x"}"><i>${s[3]==1?"✓":s[3]==2?"!":"✕"}</i><div><b>${s[0]}</b><span>${s[1]}</span><small>${s[2]}</small></div></li>`).join("")}</ol>
<p class="rcf">${ok?"Record stored in the audit log. Operator is protected from false dumping claims.":"A ward officer reviews every flag. No operator is penalised automatically."}</p>
<div class="row"><button class="btn g" onclick="closeReceipt();say('Receipt link copied: naliwatch.in/v/${tr.id}')">Copy verify link</button><button class="btn" onclick="closeReceipt()">Close</button></div></div></div>`}
function closeReceipt(){const el=$("#rcpt");if(el)el.innerHTML=""}
addEventListener("keydown",e=>{if(e.key=="Escape")closeReceipt()});
