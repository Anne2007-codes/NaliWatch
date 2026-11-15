// Mock data for one ward (tanks, reports, clusters, operators, trips, flags) and scoring helpers.
// Seeded so every screen has something real to show in a demo. Map coordinates are x 0-600, y 0-400 (see ll2()).
const tanks=[
{id:"T-101",own:1,addr:"12 Lane 3",x:120,y:110,cap:2000,occ:5,due:-12},
{id:"T-102",own:1,addr:"Shop 4, Market Rd",x:300,y:90,cap:3000,occ:8,due:18},
{id:"T-103",addr:"7 Temple Gali",x:210,y:200,cap:2500,occ:6,due:40,last:"2 days ago"},
{id:"T-104",addr:"22 Lane 5",x:150,y:260,cap:1800,occ:4,due:-3},
{id:"T-105",addr:"Canal side 9",x:430,y:150,cap:3200,occ:9,due:120},
{id:"T-106",addr:"41 Station Rd",x:480,y:260,cap:2200,occ:5,due:5},
{id:"T-107",addr:"3 Garden Lane",x:330,y:300,cap:2000,occ:3,due:210},
{id:"T-108",addr:"15 Lane 2",x:90,y:180,cap:2400,occ:7,due:2},
{id:"T-109",addr:"8 Lane 3",x:140,y:135,cap:2000,occ:6,due:-6},
{id:"T-110",addr:"19 Lane 3",x:108,y:150,cap:2200,occ:5,due:-1},
{id:"T-111",addr:"Dairy Colony 2",x:370,y:70,cap:2600,occ:6,due:64},
{id:"T-112",addr:"31 Market Rd",x:260,y:120,cap:3000,occ:7,due:9},
{id:"T-113",addr:"5 Mandir Marg",x:240,y:170,cap:2000,occ:4,due:75},
{id:"T-114",addr:"14 Lane 5",x:175,y:285,cap:2400,occ:6,due:-9},
{id:"T-115",addr:"2 School Rd",x:300,y:215,cap:2800,occ:7,due:140},
{id:"T-116",addr:"Canal side 21",x:455,y:185,cap:2600,occ:6,due:22},
{id:"T-117",addr:"9 Station Rd",x:510,y:225,cap:2000,occ:5,due:88},
{id:"T-118",addr:"27 Garden Lane",x:360,y:330,cap:2200,occ:4,due:170},
{id:"T-119",addr:"6 Ward Office Rd",x:395,y:250,cap:3500,occ:10,due:31},
{id:"T-120",addr:"18 Lane 2",x:70,y:215,cap:1800,occ:3,due:55},
{id:"T-121",addr:"44 Lane 4",x:95,y:300,cap:2000,occ:5,due:12},
{id:"T-122",addr:"11 Temple Gali",x:195,y:225,cap:2400,occ:6,due:3},
{id:"T-123",addr:"Bus Stand Rd 7",x:420,y:315,cap:3000,occ:8,due:96},
{id:"T-124",addr:"26 Dairy Colony",x:335,y:45,cap:2200,occ:5,due:190}];
const reports=[
{id:"R-21",type:"overflow",sev:3,conf:.91,x:125,y:125,age:2,why:"Sewage pooling on the lane; tank cover displaced."},
{id:"R-22",type:"dumping",sev:3,conf:.84,x:520,y:330,age:1,why:"Tanker discharging into an open drain."},
{id:"R-23",type:"manual",sev:3,conf:.88,x:215,y:215,age:0,why:"Worker enters a tank with no gear."},
{id:"R-24",type:"overflow",sev:2,conf:.72,x:160,y:250,age:4,why:"Wet patch near a tank cover."},
{id:"R-25",type:"overflow",sev:1,conf:.66,x:440,y:140,age:6,why:"Damp wall, cause unclear."},
{id:"R-26",type:"overflow",sev:3,conf:.89,x:112,y:140,age:1,why:"Foul liquid running along the lane drain."},
{id:"R-27",type:"overflow",sev:2,conf:.77,x:180,y:270,age:3,why:"Overflow stain around the inspection cover."},
{id:"R-28",type:"overflow",sev:2,conf:.74,x:305,y:100,age:5,why:"Pooling water outside a shop, smell reported."}];
const clusters=[{id:"C-1",x:130,y:150,r:70,score:82,note:"Failures and 9 sickness cases overlap"},{id:"C-2",x:190,y:245,r:55,score:61,note:"3 overflow reports close together"}];
// ASHA worker counts: areas only, never patient names
const health=[{area:"Lane 3",x:125,y:130,n:5,sym:"Diarrhoea, vomiting"},{area:"Lane 3 east",x:150,y:165,n:4,sym:"Diarrhoea, fever"},{area:"Lane 5",x:190,y:250,n:2,sym:"Skin rash"},{area:"Canal side",x:440,y:160,n:1,sym:"Fever"}];
const areas={"Lane 3":[125,130],"Market Rd":[300,100],"Canal side":[440,160],"Station Rd":[480,270]};
const PLANT={x:540,y:350};
const inC=o=>clusters.some(c=>Math.hypot(o.x-c.x,o.y-c.y)<c.r);
const score=(o,r)=>r?o.sev*20+o.age*2+(o.type=="manual"?100:0)+(inC(o)?15:0):(o.due<0?50+Math.min(-o.due,30):Math.max(0,30-o.due))+(inC(o)?15:0);
const dueTxt=d=>d<0?`Overdue ${-d} days`:d==0?"Due today":`Due in ${d} days`;
const dueCls=d=>d<0?"t-r":d<30?"t-y":"t-g";
// first version of the estimator: capacity x fill limit / (occupants x sludge per person per day); constants are placeholders
const est=(cap,occ)=>Math.round(cap*0.7/(Math.max(occ,1)*0.15));
const typeName={overflow:"Overflow",dumping:"Dumping",manual:"Manual cleaning"};
const ops=[{n:"GreenFlow Desludgers",c:"HR-DS-0412",v:"2027-03-31",s:"Valid"},{n:"Clean Tank Services",c:"HR-DS-0188",v:"2026-12-05",s:"Expiring"},{n:"Jal Seva Co.",c:"HR-DS-0097",v:"2026-09-30",s:"Expired"}];
const plants=[{n:"Hisar STP 1",a:"HSP-2210",g:"150 m geofence",v:"2028-01-01"}];
const drivers=["Ramesh","Sunil","Imran"],vehs=[["HR-20-1123",4000],["HR-20-4410",6000]];
let tol=5,dv="Ramesh",fs=null;
const audit=[["09:12","Admin added plant Hisar STP 1"],["09:05","Officer decided on F-3: Cleared: GPS fault"],["08:50","TR-291 verified at plant"]];
// Seeded trips: verified, flagged (open), flagged (closed), one waiting at the plant gate, one planned for the driver app
const trips=[
{id:"TR-285",driver:"Sunil",veh:"HR-20-4410",stops:[{k:"T-103",vol:1500,d:1}],st:"verified",recv:1480,gap:0},
{id:"TR-286",driver:"Imran",veh:"HR-20-1123",stops:[{k:"T-120",vol:1100,d:1}],st:"flagged",recv:1090,gap:11},
{id:"TR-288",driver:"Sunil",veh:"HR-20-4410",stops:[{k:"T-111",vol:1600,d:1},{k:"T-124",vol:1300,d:1}],st:"flagged",recv:2450,gap:0},
{id:"TR-290",driver:"Imran",veh:"HR-20-1123",stops:[{k:"T-105",vol:1900,d:1},{k:"T-107",vol:2000,d:1}],st:"flagged",recv:null,gap:14},
{id:"TR-291",driver:"Ramesh",veh:"HR-20-4410",stops:[{k:"T-113",vol:1200,d:1},{k:"T-115",vol:1700,d:1}],st:"verified",recv:2890,gap:0},
{id:"TR-293",driver:"Sunil",veh:"HR-20-4410",stops:[{k:"T-116",vol:1500,d:1},{k:"T-119",vol:2100,d:1}],st:"arrived",recv:null,gap:0},
{id:"TR-294",driver:"Ramesh",veh:"HR-20-1123",stops:[{k:"T-112",vol:1800,d:0},{k:"T-108",vol:1400,d:0}],st:"planned",recv:null,gap:0}];
const flags=[
{id:"F-1",trip:"TR-290",why:"Plant skipped: no plant confirmation and a 14 min GPS gap",st:"open"},
{id:"F-2",trip:"TR-288",why:"Volume mismatch: 2900 L pumped, 2450 L received (15.5%)",st:"open"},
{id:"F-3",trip:"TR-286",why:"GPS gap of 11 min near the highway, volume matched",st:"closed",dec:"Cleared: GPS fault"}];
// tanks already used by seeded trips are not open jobs
trips.forEach(tr=>tr.stops.forEach(s=>{const o=tanks.find(x=>x.id==s.k);if(o)o.job="trip"}));
const aud=a=>audit.unshift([new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}),a]);
const pumped=tr=>tr.stops.reduce((a,s)=>a+s.vol,0);
const stTag=s=>`<span class="tag ${s=="verified"?"t-g":s=="flagged"?"t-r":"t-y"}">${s}</span>`;
const pend=()=>tanks.filter(x=>(x.due<=5||x.booked)&&!x.job);
// map coordinates: the ward sits around Hisar; ll2() turns the x/y sketch coordinates into [lng,lat]
const ll2=(x,y)=>[75.703+x/600*0.034,29.1665-y/400*0.022];
