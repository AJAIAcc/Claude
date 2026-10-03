import {createCanvas,registerFont} from 'canvas';
import fs from 'fs';
import {makePaper,makeGrain,deckle} from './core/paper.mjs';
import {PAL,rgba} from './core/palette.mjs';
import {SCENES} from './scenes.mjs';
import {SECTIONS,sectionAt,DUR} from './timeline.mjs';
import {clamp,smoothstep} from './core/noise.mjs';

let FONTS=false;
export function initFonts(root='.'){
  if(FONTS)return; FONTS=true;
  const F=root+'/assets/fonts/';
  [['limelight-latin-400-normal','Limelight',400],
   ['josefin-sans-latin-700-normal','Josefin',700],
   ['josefin-sans-latin-600-normal','Josefin',600],
   ['josefin-sans-latin-400-normal','Josefin',400],
   ['bodoni-moda-latin-400-italic','BodoniI',400],
   ['bodoni-moda-latin-700-normal','Bodoni',700],
   ['playfair-display-latin-900-normal','Playfair',900],
   ['anton-latin-400-normal','Anton',400],
   ['archivo-black-latin-400-normal','Archivo',400],
   ['poiret-one-latin-400-normal','Poiret',400],
  ].forEach(([f,fam,w])=>{ try{registerFont(F+f+'.ttf',{family:fam,weight:String(w)});}catch(e){} });
}

// precompute line durations
const LINES=[];
for(const s of SECTIONS){
  s.lines.forEach((l,i)=>{
    const next = i+1<s.lines.length ? s.lines[i+1].t : s.t1;
    LINES.push({...l,sec:s.id,dur:Math.max(0.5,Math.min(next-l.t, 4.2))});
  });
}
const BY_SEC={}; for(const l of LINES){(BY_SEC[l.sec]??=[]).push(l);}

export function createRenderer(W,H,{root='.',grainN=8}={}){
  initFonts(root);
  const drive=JSON.parse(fs.readFileSync(root+'/analysis/drive.json','utf8'));
  const paper=makePaper(W,H,{seed:11});
  const grains=makeGrain(W,H,grainN,{amount:0.052});
  const c=createCanvas(W,H), x=c.getContext('2d');
  x.patternQuality='good'; x.quality='good';

  const at=(arr,f)=>arr[Math.min(arr.length-1,Math.max(0,f))];

  function env(t){
    const f=Math.round(t*drive.fps);
    const sec=sectionAt(t);
    const bands={}; for(const k in drive.bands) bands[k]=at(drive.bands[k],f);
    // beat pulse: decaying spike on each beat
    let bp=0;
    for(let i=drive.beats.length-1;i>=0;i--){
      const d=t-drive.beats[i];
      if(d>=0&&d<0.42){bp=Math.pow(1-d/0.42,2.4);break;}
      if(d<0&&i===0)break;
      if(d>=0.42)break;
    }
    const act=(BY_SEC[sec.id]||[]).filter(l=>t>=l.t && t<l.t+l.dur);
    return {
      t, f, sec, paper, bands, flux:at(drive.flux,f), vocal:at(drive.vocal,f),
      beatPulse:bp, sp:(t-sec.t0)/Math.max(0.001,sec.t1-sec.t0),
      machine: clamp((t-60)/150,0,1),
      active: act,
      spokenIdx:(l)=>(BY_SEC['spoken']||[]).findIndex(q=>q.t===l.t),
    };
  }

  function drawFrame(t){
    const E=env(t);
    x.save(); x.globalCompositeOperation='source-over'; x.globalAlpha=1;
    x.fillStyle=PAL.night; x.fillRect(0,0,W,H); x.restore();
    const fn=SCENES[E.sec.scene];
    if(fn) fn(x,W,H,E); else x.drawImage(paper,0,0);
    // grain boil at 15fps, and the deckled paper edge
    x.save(); x.globalCompositeOperation='overlay'; x.globalAlpha=0.40;
    x.drawImage(grains[Math.floor(E.f/2)%grains.length],0,0); x.restore();
    deckle(x,W,H,{inset:0,amp:Math.round(W*0.0045),col:PAL.paper});
    return c;
  }
  return {drawFrame,canvas:c,ctx:x,env,LINES};
}
