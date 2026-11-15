// Login, route table and router
function login(){const p=$("#ph1").value.trim();if(logged)return;if(!otp){if(p.replace(/\D/g,"").length<10)return say("Enter a 10-digit number");phone=p;otp=true;modal();$("#ot").focus();return}if(($("#ot").value||"").length<4)return say("Enter the 4-digit code");logged=true;sgn=false;go(rs0)}
const V={home:homeV,household,report,asha,bot,officer,operator:opV,driver:driverV,plant:plantV,flags:flagsV,admin:adminV,pub:pubV};
function draw(){const k=(location.hash||"#home").slice(1);const f=V[k]||homeV;const a=document.activeElement&&document.activeElement.id,pos=window.scrollY;nav();modal();$("#v").innerHTML=banner(k)+f()+(toast?`<div class="toast" role="status">${esc(toast)}</div>`:"");if(a&&$("#"+a)&&$("#"+a).tagName!="BUTTON")$("#"+a).focus();updateMap();demoUI();window.scrollTo(0,pos)}
addEventListener("hashchange",()=>{sel=null;const v=$("#v");v.classList.add("pg");draw();reveal();scrollTo(0,0);setTimeout(()=>v.classList.remove("pg"),700)});draw();reveal();
addEventListener("keydown",e=>{if(e.key=="Escape"&&sgn)cl()});
