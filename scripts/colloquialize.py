#!/usr/bin/env python3
"""Convert written Persian lesson content to spoken Tehrani using the maps in scripts/.
Idempotent: run after any content regeneration.  Hebrew fields are never touched.
Keeps exercises consistent: words == tokens(ru), fill_blank answer in options, distractors != correct words.
Usage: python3 scripts/colloquialize.py [--dry]"""
import json,re,sys,os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=os.path.join(ROOT,'data'); S=os.path.join(ROOT,'scripts')
M=json.load(open(os.path.join(S,'fa_colloquial_map.json')))['map']
FB=json.load(open(os.path.join(S,'fa_colloquial_fb.json')))['map']
NORM=[(r'(?<![آ-ی])(ن?)می‌آ(م|ی|د|ن|یم)(?![آ-ی])',lambda mm:mm.group(1)+'میا'+mm.group(2))]
def norm(s):
    for a,b in NORM: s=re.sub(a,b,s)
    return s
M={k:norm(v) for k,v in M.items()}
PUN=re.compile(r'[.,!?؟،؛:«»"()]')
def tok(s): return PUN.sub(' ',s).split()
def conv(s):
    if not isinstance(s,str): return s
    t=s.strip()
    if t in M: return M[t]
    return s
VOWEND=tuple('ها')
stats={'ru':0,'fb':0,'fb_skip':0,'dist_drop':0,'acc_add':0}
def fix_fb(ex):
    key=ex['sentence']+'|'+ex['answer']
    if key not in FB: return
    sen,ans,opts=FB[key]; opts=[norm(o) for o in opts]; sen=norm(sen); ans=norm(ans)
    if ans in ('ـه','ه'):  # copula: attach the blank to the previous word
        sen=re.sub(r'\s*___',"___",sen)
        prev=sen.split('___')[0].split()[-1] if sen.split('___')[0].split() else ''
        if prev.endswith(VOWEND) and prev not in ('ده','که','به'): sen=sen.replace('___','‌___'); new='ست'
        else: new='ه'
        opts=[new if o==ans else o for o in opts]; ans=new
    if sen.count('___')!=1 or ans not in opts or len(set(opts))!=len(opts) or len(opts)<2:
        stats['fb_skip']+=1; return
    ex['sentence']=sen; ex['answer']=ans
    ex['options']=[{'ru':o,'correct':o==ans} for o in opts]; stats['fb']+=1
def walk(o):
    if isinstance(o,list):
        for x in o: walk(x)
        return
    if not isinstance(o,dict): return
    if o.get('type')=='alphabet': return
    if o.get('type')=='fill_blank': fix_fb(o); return
    if 'ru' in o and isinstance(o['ru'],str):
        n=conv(o['ru'])
        if n!=o['ru']: o['ru']=n; stats['ru']+=1
        if 'words' in o and isinstance(o['words'],list):
            o['words']=tok(o['ru'])
            if 'wordsHeTranslit' in o: del o['wordsHeTranslit']
    if 'model' in o: o['model']=conv(o['model'])
    if isinstance(o.get('accepted'),list):
        add=[conv(a) for a in o['accepted'] if conv(a)!=a]
        for a in add:
            if a not in o['accepted']: o['accepted'].append(a); stats['acc_add']+=1
    if isinstance(o.get('distractors'),list):
        good=set(o.get('words') or tok(o.get('ru','')))
        nd=[]
        for d in o['distractors']:
            d2=conv(d)
            if d2 in good or d2 in nd: stats['dist_drop']+=1; continue
            nd.append(d2)
        if nd: o['distractors']=nd
    for k,v in o.items():
        if k not in ('words','distractors','accepted') and isinstance(v,(dict,list)): walk(v)
START=re.compile(r'(window\.RL_\w+=|\.concat\()')
def process(fn,dry):
    p=os.path.join(D,fn); s=open(p,encoding='utf8').read(); out=[];i=0
    for mm in START.finditer(s):
        if mm.start()<i: continue
        j=mm.end(); obj,end=json.JSONDecoder().raw_decode(s,j)
        walk(obj); out.append(s[i:j]); out.append(json.dumps(obj,ensure_ascii=False,separators=(',',':'))); i=end
    out.append(s[i:]); ns=''.join(out)
    if ns!=s and not dry: open(p,'w',encoding='utf8').write(ns)
    return ns!=s
if __name__=='__main__':
    dry='--dry' in sys.argv
    files=[f for f in sorted(os.listdir(D)) if re.match(r'^([abc]\d-part\d|grammar|conversations|dialogues)\.js$',f)]
    ch=[f for f in files if process(f,dry)]
    print('changed files:',ch); print(stats)
