#!/usr/bin/env python3
"""Interactive AA/state comparison page (slider, strips, blink, diff) from collect_shots.py output dirs.
Usage (needs numpy, pillow, imagecodecs):
  make_slider.py --out work/aa_compare --set "DLAA/FXAA modes=work/aa_modes" --set "Falloff=work/aa_falloff" [--scenes a b ...] [--html-only]
Writes <out>/index.html, data.js and img/*.webp (lossless 1080p-equivalent via 2x2 box reduce, same as analyze_ab.py; zoom shows the pixels crisp).  Open index.html (double click) for slider /
strips / blink; the diff mode needs the page served over http (canvas pixel access): run <out>/serve.sh and open http://localhost:8765."""
import sys, os, json
import numpy as np
from PIL import Image, ImageFilter
import imagecodecs
args = sys.argv[1:]
opt = lambda k, many=False: [args[i + 1] for i, x in enumerate(args) if x == k] if many else (args[args.index(k) + 1] if k in args else None)
out = opt("--out") or os.path.join(os.environ.get("PS5_WORKDIR", "work"), "aa_compare"); sets = opt("--set", True); keep = None
if "--scenes" in args:
    i = args.index("--scenes") + 1; keep = []
    while i < len(args) and not args[i].startswith("--"): keep.append(args[i]); i += 1
os.makedirs(os.path.join(out, "img"), exist_ok=True)
def sharp(l):
    lap = np.abs(4 * l[1:-1, 1:-1] - l[:-2, 1:-1] - l[2:, 1:-1] - l[1:-1, :-2] - l[1:-1, 2:])
    bl = np.asarray(Image.fromarray(np.clip(l, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), dtype=np.float32)[1:-1, 1:-1]
    r = lap / (bl + 8); return float(r.mean()), float(r[int(r.shape[0] * 0.6):].mean())
slug = lambda s: "".join(c if c.isalnum() else "_" for c in s).strip("_")
data = {"sets": []}
html_only = "--html-only" in args
if html_only: data = json.loads(open(os.path.join(out, "data.js")).read()[len("window.DATA = "):].rstrip().rstrip(";")); sets = []
for spec in sets:
    label, d = spec.split("=", 1); man = json.load(open(os.path.join(d, "manifest.json"))); scenes = []
    for sc in dict.fromkeys(x["scene"] for x in man):
        if keep and sc not in keep: continue
        states = []
        for st in dict.fromkeys(x["state"] for x in man if x["scene"] == sc):
            x = [m for m in man if m["scene"] == sc and m["state"] == st][0]
            rgb = imagecodecs.jpegxr_decode(open(os.path.join(d, x["file"] + ".jxr"), "rb").read())[..., :3]
            im = Image.fromarray(rgb).reduce(2); fn = "img/%s__%s__%s.webp" % (slug(label), slug(sc), slug(st))
            im.save(os.path.join(out, fn), "WEBP", lossless=True, quality=100, method=3)
            s, g = sharp(np.asarray(im.convert("L"), dtype=np.float32)); states.append({"name": st, "file": fn, "sharp": round(s, 4), "ground": round(g, 4)}); print(label, sc, st, "%.4f" % s, flush=True)
        scenes.append({"name": sc, "states": states})
    data["sets"].append({"name": label, "scenes": scenes})
if not html_only: open(os.path.join(out, "data.js"), "w").write("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
open(os.path.join(out, "serve.sh"), "w").write('#!/bin/sh\ncd "$(dirname "$0")" && echo "http://localhost:8765" && python3 -m http.server 8765\n'); os.chmod(os.path.join(out, "serve.sh"), 0o755)
HTML = r'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Bloodborne AA comparison</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#14161a;color:#e6e6e6;font:14px/1.4 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif;height:100vh;display:flex;flex-direction:column}
header{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:end;padding:8px 14px;background:#1d2026;border-bottom:1px solid #2c3038}
label{display:flex;flex-direction:column;gap:3px;font-size:12px;color:#aab}select,button,input[type=range]{background:#2a2e36;color:#eee;border:1px solid #3b414c;border-radius:6px;padding:6px 8px;font:inherit}
input[type=range]{padding:0;height:30px;width:120px;accent-color:#7aa7ff}button{cursor:pointer}button:hover{background:#343944}.hide{display:none!important}
#viewer{position:relative;flex:1;min-height:300px;overflow:hidden;background:#000;touch-action:none;cursor:grab;user-select:none;-webkit-user-select:none}#viewer.pan{cursor:grabbing}
#stage{position:absolute;left:0;top:0;width:1920px;height:1080px;transform-origin:0 0}.layer{position:absolute;left:0;top:0;width:1920px;height:1080px;display:block}
.sep{position:absolute;background:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.6)}
#handle{position:absolute;top:0;bottom:0;width:36px;margin-left:-18px;cursor:ew-resize;z-index:5}#handle::before{content:"";position:absolute;left:17px;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.6)}
#handle::after{content:"\2194";position:absolute;left:0;top:50%;width:36px;height:36px;margin-top:-18px;border-radius:50%;background:#fff;color:#111;font-size:20px;line-height:36px;text-align:center}
.tag{position:absolute;padding:4px 10px;background:rgba(0,0,0,.75);border-radius:6px;font-size:14px;font-weight:600;z-index:4;pointer-events:none;white-space:nowrap}
#info{padding:6px 14px 10px;color:#99a;font-size:13px;background:#14161a;border-top:1px solid #2c3038}#info b{color:#ccd}kbd{background:#2a2e36;border:1px solid #3b414c;border-radius:4px;padding:0 5px}
#msg{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,.85);padding:14px 20px;border-radius:8px;z-index:9;max-width:520px;text-align:center}
</style></head><body>
<header>
<label>Set<select id="set"></select></label><label>Scene<select id="scene"></select></label>
<label>Mode<select id="mode"><option value="slider">Slider (A | B)</option><option value="vstrips">Vertical strips (A–D)</option><option value="hstrips">Horizontal strips (A–D)</option><option value="blink">Blink (A / B)</option><option value="diff">Difference |A − B|</option></select></label>
<label>A<select id="selA"></select></label><label>B<select id="selB"></select></label><label id="lblC">C<select id="selC"></select></label><label id="lblD">D<select id="selD"></select></label>
<label id="lblRate">Blink interval<select id="rate"><option value="400">0.4 s</option><option value="800" selected>0.8 s</option><option value="1500">1.5 s</option></select></label>
<label id="lblGain"><span>Difference gain: <b id="gainVal">8</b>×</span><input type="range" id="gain" min="1" max="40" value="8"></label>
<button id="fit">Fit to window</button><button id="z1">100 %</button><button id="z2">200 %</button><button id="z4">400 %</button>
</header>
<div id="viewer"><div id="stage"></div><div id="handle"></div><div class="tag" id="tagA" style="left:8px;top:8px"></div><div class="tag" id="tagB" style="right:8px;top:8px"></div><div id="msg" class="hide"></div></div>
<div id="info"></div>
<script src="data.js"></script>
<script>
const $=id=>document.getElementById(id), W=1920, H=1080; let S={set:0,scene:0,mode:'slider',a:0,b:1,c:-1,d:-1,split:.5,s:1,tx:0,ty:0}, blinkT=null, blinkOn=false;
const cur=()=>DATA.sets[S.set].scenes[S.scene], st=i=>cur().states[i];
function fill(sel,opts,none){sel.innerHTML=(none?'<option value="-1">–</option>':'')+opts.map((n,i)=>`<option value="${i}">${n}</option>`).join('')}
function initSets(){fill($('set'),DATA.sets.map(x=>x.name));initScenes()}
function initScenes(){fill($('scene'),cur?DATA.sets[S.set].scenes.map(x=>x.name):[]);S.scene=0;$('scene').value=0;initStates()}
function initStates(){const n=cur().states.map(x=>x.name);['selA','selB'].forEach(i=>fill($(i),n));['selC','selD'].forEach(i=>fill($(i),n,true));S.a=0;S.b=Math.min(1,n.length-1);S.c=-1;S.d=-1;$('selA').value=S.a;$('selB').value=S.b;$('selC').value=-1;$('selD').value=-1;fit();render()}
function applyT(){$('stage').style.transform=`translate(${S.tx}px,${S.ty}px) scale(${S.s})`;const pix=S.s>1.5?'pixelated':'auto';document.querySelectorAll('.layer').forEach(l=>l.style.imageRendering=pix);placeHandle()}
function fit(){const v=$('viewer');S.s=Math.min(v.clientWidth/W,v.clientHeight/H);S.tx=(v.clientWidth-W*S.s)/2;S.ty=(v.clientHeight-H*S.s)/2;applyT()}
function zoomTo(z,cx,cy){const v=$('viewer'),r=v.getBoundingClientRect();cx=cx??r.width/2;cy=cy??r.height/2;const k=z/S.s;S.tx=cx-(cx-S.tx)*k;S.ty=cy-(cy-S.ty)*k;S.s=z;applyT()}
function placeHandle(){const h=$('handle');h.classList.toggle('hide',S.mode!=='slider');h.style.left=(S.tx+S.split*W*S.s)+'px'}
function img(i){const e=document.createElement('img');e.className='layer';e.src=st(i).file;e.draggable=false;return e}
function sel(){return [S.a,S.b,S.c,S.d].filter(x=>x>=0)}
function render(){clearInterval(blinkT);$('msg').classList.add('hide');const g=$('stage');g.innerHTML='';const m=S.mode;
 ['lblC','lblD'].forEach(i=>$(i).classList.toggle('hide',m!=='vstrips'&&m!=='hstrips'));$('lblRate').classList.toggle('hide',m!=='blink');$('lblGain').classList.toggle('hide',m!=='diff');
 const A=img(S.a),B=img(S.b);let tA=st(S.a).name,tB=st(S.b).name;$('tagB').classList.remove('hide');
 if(m==='slider'){g.append(A,B);B.style.clipPath=`inset(0 0 0 ${S.split*W}px)`}
 else if(m==='blink'){g.append(A,B);B.style.opacity=0;blinkOn=false;blinkT=setInterval(()=>{blinkOn=!blinkOn;B.style.opacity=blinkOn?1:0;$('tagA').textContent='A: '+(blinkOn?tB:tA);$('tagA').style.background=blinkOn?'rgba(122,167,255,.85)':'rgba(0,0,0,.75)'},+$('rate').value);$('tagB').classList.add('hide')}
 else if(m==='vstrips'||m==='hstrips'){const ids=sel(),n=ids.length;ids.forEach((id,k)=>{const L=img(id);g.append(L);L.style.clipPath=m==='vstrips'?`inset(0 ${W-(k+1)*W/n}px 0 ${k*W/n}px)`:`inset(${k*H/n}px 0 ${H-(k+1)*H/n}px 0)`;
   const t=document.createElement('div');t.className='tag';t.style.cssText=m==='vstrips'?`left:${k*W/n+10}px;top:10px;font-size:34px;transform-origin:0 0`:`left:10px;top:${k*H/n+10}px;font-size:34px`;t.textContent='ABCD'[k]+': '+st(id).name;g.append(t);
   if(k>0){const s=document.createElement('div');s.className='sep';s.style.cssText=m==='vstrips'?`left:${k*W/n-1}px;top:0;width:3px;height:${H}px`:`top:${k*H/n-1}px;left:0;height:3px;width:${W}px`;g.append(s)}});$('tagA').classList.add('hide');$('tagB').classList.add('hide')}
 else if(m==='diff'){const c=document.createElement('canvas');c.width=W;c.height=H;c.className='layer';g.append(c);diffDraw(c)}
 if(m!=='vstrips'&&m!=='hstrips'){$('tagA').classList.remove('hide');if(m!=='blink'){$('tagA').textContent='A: '+tA;$('tagA').style.background='rgba(0,0,0,.75)'}$('tagB').textContent='B: '+tB;if(m==='diff')$('tagB').classList.add('hide')}
 applyT();info()}
function diffDraw(c){const a=new Image(),b=new Image();let n=0;const go=()=>{if(++n<2)return;const x=document.createElement('canvas');x.width=W;x.height=H;const X=x.getContext('2d');X.drawImage(a,0,0);let da;try{da=X.getImageData(0,0,W,H)}catch(e){$('msg').textContent='The difference view needs a web server (browsers block reading image pixels on file:// URLs). Run serve.sh and open http://localhost:8765';$('msg').classList.remove('hide');return}
  X.clearRect(0,0,W,H);X.drawImage(b,0,0);const db=X.getImageData(0,0,W,H),o=c.getContext('2d').createImageData(W,H),G=+$('gain').value;for(let i=0;i<da.data.length;i+=4){const d=Math.min(255,(Math.abs(da.data[i]-db.data[i])+Math.abs(da.data[i+1]-db.data[i+1])+Math.abs(da.data[i+2]-db.data[i+2]))/3*G);o.data[i]=o.data[i+1]=o.data[i+2]=d;o.data[i+3]=255}c.getContext('2d').putImageData(o,0,0)};
 a.onload=b.onload=go;a.src=st(S.a).file;b.src=st(S.b).file}
function info(){const A=st(S.a),B=st(S.b),p=(x,y)=>(y>=x?'+':'')+((y-x)/x*100).toFixed(1)+' %';$('info').innerHTML=`<b>A</b>: ${A.name} — sharpness ${A.sharp}, ground ${A.ground} &nbsp;|&nbsp; <b>B</b>: ${B.name} — sharpness ${B.sharp}, ground ${B.ground} &nbsp;|&nbsp; B vs A: sharpness <b>${p(A.sharp,B.sharp)}</b>, ground <b>${p(A.ground,B.ground)}</b><br>Mouse wheel = zoom, drag = pan, double-click = fit. <kbd>←</kbd><kbd>→</kbd> slider, <kbd>Space</kbd> pauses blink, <kbd>1</kbd>–<kbd>9</kbd> picks B. Images are 1080p (the game's real pixels); zoom shows them as crisp pixels.`}
$('set').onchange=e=>{S.set=+e.target.value;initScenes()};$('scene').onchange=e=>{S.scene=+e.target.value;initStates()};$('mode').onchange=e=>{S.mode=e.target.value;render()};
['A','B','C','D'].forEach(k=>$('sel'+k).onchange=e=>{S[k.toLowerCase()]=+e.target.value;render()});$('rate').onchange=render;$('gain').oninput=e=>{$('gainVal').textContent=e.target.value;render()};
$('fit').onclick=fit;$('z1').onclick=()=>zoomTo(1);$('z2').onclick=()=>zoomTo(2);$('z4').onclick=()=>zoomTo(4);
const V=$('viewer');V.addEventListener('wheel',e=>{e.preventDefault();const r=V.getBoundingClientRect();zoomTo(Math.max(.2,Math.min(12,S.s*(e.deltaY<0?1.2:1/1.2))),e.clientX-r.left,e.clientY-r.top)},{passive:false});V.addEventListener('dblclick',fit);
let drag=null;V.addEventListener('pointerdown',e=>{V.setPointerCapture(e.pointerId);if(e.target.id==='handle')drag={t:'h'};else{drag={t:'p',x:e.clientX,y:e.clientY,tx:S.tx,ty:S.ty};V.classList.add('pan')}});
V.addEventListener('pointermove',e=>{if(!drag)return;if(drag.t==='h'){const r=V.getBoundingClientRect();S.split=Math.max(0,Math.min(1,(e.clientX-r.left-S.tx)/(W*S.s)));$('stage').querySelectorAll('.layer')[1].style.clipPath=`inset(0 0 0 ${S.split*W}px)`;placeHandle()}else{S.tx=drag.tx+e.clientX-drag.x;S.ty=drag.ty+e.clientY-drag.y;applyT()}});
V.addEventListener('pointerup',()=>{drag=null;V.classList.remove('pan')});window.addEventListener('resize',fit);
window.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){S.split=Math.max(0,Math.min(1,S.split+(e.key==='ArrowLeft'?-.02:.02)));render()}else if(e.key===' '){e.preventDefault();if(blinkT){clearInterval(blinkT);blinkT=null}else render()}else if(e.key>='1'&&e.key<='9'){const i=+e.key-1;if(i<cur().states.length){S.b=i;$('selB').value=i;render()}}});
initSets();
(function(){const h=new URLSearchParams(location.hash.slice(1));if(!h.size)return;const num=k=>h.has(k)?+h.get(k):null;
 if(num('set')!=null){S.set=num('set');$('set').value=S.set;initScenes()}if(num('scene')!=null){S.scene=num('scene');$('scene').value=S.scene;initStates()}
 if(h.get('mode')){S.mode=h.get('mode');$('mode').value=S.mode}for(const k of ['a','b','c','d'])if(num(k)!=null){S[k]=num(k);$('sel'+k.toUpperCase()).value=S[k]}
 if(num('split')!=null)S.split=num('split');render();if(num('zoom')!=null){zoomTo(num('zoom'),num('zx')??undefined,num('zy')??undefined)}})();
</script></body></html>'''
open(os.path.join(out, "index.html"), "w").write(HTML); print("wrote", os.path.join(out, "index.html"), "sets", len(data["sets"]))
