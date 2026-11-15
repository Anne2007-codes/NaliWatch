// Login, route table and router
const ROLE_VIEW={household:"household",reporter:"report",asha:"asha",officer:"officer",admin:"admin",operator:"operator",driver:"driver",plant:"plant"};
async function login(){
  const p=$("#ph1").value.trim();if(logged)return;
  if(!otp){
    if(p.replace(/\D/g,"").length<10)return say("Enter a 10-digit number");
    phone=p;
    try{
      const r=await api.requestOtp(p);
      otp=true;modal();
      if(r.dev_otp) say("Dev OTP: "+r.dev_otp);
      const ot=$("#ot");if(ot)ot.focus();
    }catch(e){say(e.message||"Could not send code")}
    return;
  }
  const code=($("#ot").value||"").trim();
  if(code.length<6)return say("Enter the 6-digit code");
  try{
    const r=await api.verifyOtp(phone,code,{language:lang,consent:true});
    api.setSession(r.access_token,r.user);
    logged=true;sgn=false;rs0=ROLE_VIEW[r.user.role]||rs0;
    await loadLive();
    go(rs0);
  }catch(e){say(e.message||"Wrong or expired code")}
}
function logout(){api.setSession("",null);logged=false;otp=false;me=null;nwLive=false;go("home")}
const V={home:homeV,household,report,asha,bot,officer,operator:opV,driver:driverV,plant:plantV,flags:flagsV,admin:adminV,pub:pubV};
function draw(){const k=(location.hash||"#home").slice(1);const f=V[k]||homeV;const a=document.activeElement&&document.activeElement.id,pos=window.scrollY;nav();modal();$("#v").innerHTML=banner(k)+f()+(toast?`<div class="toast" role="status">${esc(toast)}</div>`:"");if(a&&$("#"+a)&&$("#"+a).tagName!="BUTTON")$("#"+a).focus();updateMap();demoUI();window.scrollTo(0,pos)}
addEventListener("hashchange",()=>{sel=null;const v=$("#v");v.classList.add("pg");draw();reveal();scrollTo(0,0);setTimeout(()=>v.classList.remove("pg"),700)});
(async()=>{try{if(token){me=await api.me();api.setSession(token,me);rs0=ROLE_VIEW[me.role]||rs0;await loadLive()}}catch(e){api.setSession("",null);logged=false}draw();reveal()})();
addEventListener("keydown",e=>{if(e.key=="Escape"&&sgn)cl()});
