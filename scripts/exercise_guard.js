// Exercise integrity guard (run after scripts/colloquialize.py): node scripts/exercise_guard.js
const fs=require("fs"),path=require("path");global.window={};
const D=path.join(__dirname,"..","data");
for(const f of fs.readdirSync(D).filter(f=>/^([abc]\d-part\d|grammar|conversations|dialogues)\.js$/.test(f))) eval(fs.readFileSync(path.join(D,f),"utf8"));
const tok=s=>s.replace(/[.,!?؟،؛:«»"()]/g," ").split(/\s+/).filter(Boolean);
const errs=[];let n=0,written=0;const W=/(^|\s)(است|می‌خواهم|می‌توانم|نمی‌دانم|چیست|خانه|هستند)([\s.؟!،]|$)/;
function e(m,o){errs.push(m+" :: "+JSON.stringify(o).slice(0,200));}
function walk(o){ if(Array.isArray(o)) return o.forEach(walk); if(!o||typeof o!=="object") return;
  if(o.type){ n++;
    if(["listen_order","sentence_build","translate_he_ru"].includes(o.type)){
      if(JSON.stringify(tok(o.ru||""))!==JSON.stringify(o.words)) e("words!=tok(ru)",o);
      if(!o.words||!o.words.length) e("no words",o);
      (o.distractors||[]).forEach(d=>{ if(o.words.includes(d)) e("distractor equals a correct word",o); });
    }
    if(o.type==="fill_blank"){
      if((o.sentence.match(/___/g)||[]).length!==1) e("blank count",o);
      const c=o.options.filter(x=>x.correct); if(o.answer&&(c.length!==1||c[0].ru!==o.answer)) e("answer/options",o);
      if(new Set(o.options.map(x=>x.ru)).size!==o.options.length) e("dup options",o);
    }
    if(o.type==="listen_choice"&&o.choices.filter(x=>x.correct).length!==1) e("choice correct count",o);
    if(o.type==="match_pairs"&&new Set(o.pairs.map(p=>p.ru)).size!==o.pairs.length) e("dup pair ru",o);
    if(typeof o.ru==="string"&&W.test(o.ru)) written++;
    if(typeof o.ru==="string"&&/[\u0600-\u06ff][a-zA-Z]|[a-zA-Z][\u0600-\u06ff]/.test(o.ru)) e("latin inside persian",o);
  }
  Object.values(o).forEach(walk);}
walk(window);
const conv=window.RL_CONVERSATIONS.scenarios;conv.forEach(s=>s.steps.forEach(st=>{ if(st.choices&&st.choices.filter(c=>c.ok).length<1) e("conv no ok choice",st); }));
console.log(`exercises=${n} errors=${errs.length} written-form ru remaining=${written}`);errs.slice(0,30).forEach(x=>console.log(" -",x));
process.exit(errs.length?1:0);
