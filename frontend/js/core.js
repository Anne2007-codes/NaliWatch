// State, DOM helpers and small utilities
const $=s=>document.querySelector(s);
let lang='en',logged=false,phone='',otp=false,sel=null,toast='',busy=0;
const F={tanks:1,reports:1,clusters:1,health:1};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
