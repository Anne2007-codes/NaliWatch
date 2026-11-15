// State, DOM helpers and small utilities
const $=s=>document.querySelector(s);
let lang='en',logged=false,phone='',otp=false,sel=null,toast='',busy=0,token='',me=null,nwLive=false;
try{token=localStorage.getItem("NW_TOKEN")||"";me=JSON.parse(localStorage.getItem("NW_USER")||"null")}catch(e){token="";me=null}
if(token&&me){logged=true;phone=me.phone||"";}
const F={tanks:1,reports:1,clusters:1,health:1};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
