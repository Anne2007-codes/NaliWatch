// Real map (MapLibre GL + OpenStreetMap tiles). draw() rebuilds #v on every state change, so the map lives in a
// detached host node that is re-attached into #mapslot after each draw. Falls back to the SVG sketch if MapLibre is missing.
let MAP=null,MH=null,MK=[],MR=0,TM=null,LT=null;
const MAPOK=()=>typeof maplibregl!=="undefined";
const fcol=f=>({type:"FeatureCollection",features:f});
const circ=c=>{const a=[];for(let i=0;i<=48;i++){const t=i/48*2*Math.PI;a.push(ll2(c.x+c.r*Math.cos(t),c.y+c.r*Math.sin(t)))}return a};
const WARD=[[30,40],[560,25],[585,370],[40,385],[30,40]].map(p=>ll2(p[0],p[1]));
function mapHost(){
if(MH)return MH;MH=document.createElement("div");MH.className="mlmap";if(!MAPOK())return MH;
MH.innerHTML=`<div class="mlc"></div><div class="mlg" aria-label="Map legend"><b>Legend</b><span><i style="background:#e5472b"></i>Tank overdue</span><span><i style="background:#f2b01e"></i>Due in 30 days</span><span><i style="background:#3f9b4b"></i>On track</span><span><i class="tri"></i>Citizen report</span><span><i class="rz"></i>Risk zone</span><span class="hl"><i style="background:#9b4dca"></i>Sickness (ASHA)</span></div>`;
MAP=new maplibregl.Map({container:MH.querySelector(".mlc"),style:{version:8,sources:{osm:{type:"raster",tiles:["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],tileSize:256,maxzoom:19,attribution:"© OpenStreetMap contributors"}},layers:[{id:"bg",type:"background",paint:{"background-color":"#dcecf0"}},{id:"osm",type:"raster",source:"osm",paint:{"raster-saturation":-.35,"raster-opacity":.9}}]},center:ll2(300,205),zoom:14.1,attributionControl:{compact:true},cooperativeGestures:false});
MAP.addControl(new maplibregl.NavigationControl({showCompass:false}),"top-right");
MAP.on("style.load",()=>{
MAP.addSource("ward",{type:"geojson",data:fcol([{type:"Feature",geometry:{type:"Polygon",coordinates:[WARD]}}])});
MAP.addSource("zones",{type:"geojson",data:fcol([])});MAP.addSource("route",{type:"geojson",data:fcol([])});MAP.addSource("trail",{type:"geojson",data:fcol([])});
MAP.addLayer({id:"ward-fill",type:"fill",source:"ward",paint:{"fill-color":"#0b7f98","fill-opacity":.05}});
MAP.addLayer({id:"ward-line",type:"line",source:"ward",paint:{"line-color":"#0b7f98","line-width":2.5,"line-dasharray":[3,2]}});
MAP.addLayer({id:"zones-fill",type:"fill",source:"zones",paint:{"fill-color":"#e5472b","fill-opacity":.2}});
MAP.addLayer({id:"zones-line",type:"line",source:"zones",paint:{"line-color":"#e5472b","line-width":2.5,"line-dasharray":[2,1.5]}});
MAP.addLayer({id:"route-line",type:"line",source:"route",paint:{"line-color":"#0b7f98","line-width":4,"line-dasharray":[1.5,1.5]}});
MAP.addLayer({id:"trail-case",type:"line",source:"trail",paint:{"line-color":"#06222f","line-width":8,"line-opacity":.85},layout:{"line-cap":"round","line-join":"round"}});
MAP.addLayer({id:"trail-line",type:"line",source:"trail",paint:{"line-color":"#c8f542","line-width":4.5},layout:{"line-cap":"round","line-join":"round"}});
MR=1;updateMap()});
MAP.on("error",()=>{});return MH}
const tcol=o=>o.due<0?"#e5472b":o.due<30?"#f2b01e":"#3f9b4b";
function addMk(html,cls,x,y,id,title){const el=document.createElement("div");el.className="mk "+cls;el.innerHTML=html;if(title)el.title=title;
if(id)el.onclick=e=>{e.stopPropagation();pick(id)};MK.push(new maplibregl.Marker({element:el,anchor:"center"}).setLngLat(ll2(x,y)).addTo(MAP))}
function updateMap(){
const slot=$("#mapslot");if(!slot)return;
if(!MAPOK()){slot.outerHTML=mapSvg();return}
const h=mapHost();if(h.parentNode!==slot)slot.appendChild(h);if(!MR)return;
MAP.resize();MK.forEach(m=>m.remove());MK=[];
MAP.getSource("zones").setData(fcol(F.clusters?clusters.map(c=>({type:"Feature",properties:{id:c.id},geometry:{type:"Polygon",coordinates:[circ(c)]}})):[]));
if(F.clusters)clusters.forEach(c=>addMk(`<span class="zl">${c.score}</span>`,"zone",c.x,c.y,c.id,"Risk zone "+c.id));
if(F.health)health.forEach(o=>addMk(`<span class="hp" style="--s:${22+o.n*5}px">${o.n}</span>`,"hlt",o.x,o.y,null,`${o.area}: ${o.n} sickness cases`));
if(F.tanks)tanks.forEach(o=>addMk(`<span class="tk2 ${o.due<0?"pls":""} ${sel==o.id?"sl":""}" style="background:${tcol(o)}"></span>`,"tkm",o.x,o.y,o.id,`${o.id} · ${dueTxt(o.due)}`));
if(F.reports)reports.forEach(o=>addMk(`<span class="rp2 ${sel==o.id?"sl":""} ${o.type=="manual"?"em":""}"><svg viewBox="0 0 24 22"><path d="M12 1L23 20H1z"/><path d="M12 8v6M12 16.5v1.5"/></svg></span>`,"rpm",o.x,o.y,o.id,`${o.id} · ${typeName[o.type]}`));
addMk(`<span class="pl2">${ic("plant")}</span>`,"plm",PLANT.x,PLANT.y,null,"Hisar STP 1 · 150 m geofence")}
function mapFocus(id){const sl=$("#mapslot");if(sl)sl.scrollIntoView({behavior:"smooth",block:"start"});if(!MAP)return;const o=[...tanks,...reports,...clusters].find(x=>x.id==id);if(o)MAP.flyTo({center:ll2(o.x,o.y),zoom:15.2,duration:700})}
function tripPts(tr){return[...tr.stops.map(s=>{const o=tanks.find(x=>x.id==s.k);return[o.x,o.y]}),[PLANT.x,PLANT.y]]}
function showRoute(tr){if(!MR)return;const p=tripPts(tr).map(a=>ll2(a[0],a[1]));MAP.getSource("route").setData(fcol([{type:"Feature",geometry:{type:"LineString",coordinates:p}}]));
const b=p.reduce((b,c)=>b.extend(c),new maplibregl.LngLatBounds(p[0],p[0]));MAP.fitBounds(b,{padding:60,duration:600})}
function clearTrip(){if(MR){MAP.getSource("route").setData(fcol([]));MAP.getSource("trail").setData(fcol([]))}if(TM){TM.remove();TM=null}}
// Animate a tanker along its trip (pick-ups, then the plant). done() runs when it reaches the gate.
function playTrip(tr,done,ms){ms=ms||9000;LT={tr,p:0,label:"Starting"};const sl=$("#mapslot");if(sl)sl.scrollIntoView({behavior:"smooth",block:"start"});
const pts=tripPts(tr),ll=pts.map(a=>ll2(a[0],a[1])),seg=[0];for(let i=1;i<ll.length;i++)seg.push(seg[i-1]+Math.hypot(ll[i][0]-ll[i-1][0],ll[i][1]-ll[i-1][1]));const tot=seg[seg.length-1];
const fin=()=>{LT=null;if(TM){TM.remove();TM=null}if(MR)MAP.getSource("trail").setData(fcol([]));done&&done()};
if(!MR||!MAPOK()){let p=0;const iv=setInterval(()=>{p+=.12;LT.p=Math.min(p,1);LT.label=ltLabel(tr,LT.p,seg,tot,pts);ltDom();if(p>=1){clearInterval(iv);fin()}},ms/9);return}
showRoute(tr);const el=document.createElement("div");el.className="mk tnk";el.innerHTML=`<span class="tn">${ic("operator")}</span>`;TM=new maplibregl.Marker({element:el,anchor:"center"}).setLngLat(ll[0]).addTo(MAP);
const t0=performance.now();(function f(now){if(!LT||LT.tr!==tr)return;const p=Math.min((now-t0)/ms,1),d=p*tot;let i=1;while(i<seg.length-1&&seg[i]<d)i++;
const k=(d-seg[i-1])/Math.max(seg[i]-seg[i-1],1e-9),pos=[ll[i-1][0]+(ll[i][0]-ll[i-1][0])*k,ll[i-1][1]+(ll[i][1]-ll[i-1][1])*k];
TM.setLngLat(pos);MAP.getSource("trail").setData(fcol([{type:"Feature",geometry:{type:"LineString",coordinates:[...ll.slice(0,i),pos]}}]));
LT.p=p;LT.label=ltLabel(tr,p,seg,tot,pts);ltDom();if(p<1)requestAnimationFrame(f);else setTimeout(fin,500)})(t0)}
function ltLabel(tr,p,seg,tot,pts){const d=p*tot;for(let i=1;i<seg.length-1;i++)if(d<seg[i])return `Pick-up ${i}/${tr.stops.length}: ${tr.stops[i-1].k} · OTP confirmed`;return p>=1?"At Hisar STP 1: checking the load":"Driving to Hisar STP 1 · GPS trail on"}
function ltDom(){const l=$("#ltl"),b=$("#ltb");if(l&&LT)l.textContent=LT.label;if(b&&LT)b.style.width=Math.round(LT.p*100)+"%"}
function liveCard(){if(!LT)return "";return `<div class="card live"><h3><span class="dot"></span> Live trip ${LT.tr.id}</h3><p>${LT.tr.driver} · ${LT.tr.veh} · ${pumped(LT.tr)} L</p><div class="pg"><i id="ltb" style="width:${Math.round(LT.p*100)}%"></i></div><p id="ltl" class="ltl">${esc(LT.label)}</p></div>`}
