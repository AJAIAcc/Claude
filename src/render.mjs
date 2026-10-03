import {createCanvas,registerFont} from 'canvas';
import fs from 'fs';
import {makePaper,makeGrain,deckle} from './core/paper.mjs';
import {PAL,rgba} from './core/palette.mjs';
import {SCENES} from './scenes.mjs';
import {SECTIONS,sectionAt,DUR} from './timeline.mjs';
import {TONE} from './core/tone.mjs';
import {SCENES as _S} from './scenes.mjs';
import {clamp,smoothstep,mulberry32,noise2} from './core/noise.mjs';

const ease2=u=>1-Math.pow(1-u,4);
// Per-section cut treatment. Keyed to what the music does at that boundary.
const TRANS={
  title:      {kind:'flash', dur:0.16, a:0.85, col:'#FFF6E4'},
  verse1:     {kind:'sweep', dur:0.26, a:1,    col:'#F3EADA'},
  prechorus:  {kind:'flash', dur:0.10, a:0.55, col:'#FFF0D0'},
  chorus1:    {kind:'flash', dur:0.20, a:0.95, col:'#FFF6E4'},
  clarinet:   {kind:'sweep', dur:0.30, a:1,    col:'#EFE3CC'},
  verse3:     {kind:'dark',  dur:0.26, a:0.90, col:'#2A0F14'},
  sax:        {kind:'dark',  dur:0.22, a:0.85, col:'#160A0D'},
  machine:    {kind:'dark',  dur:0.12, a:1.00, col:'#000000'},
  chorus2:    {kind:'flash', dur:0.18, a:0.90, col:'#FFF6E4'},
  chorus3:    {kind:'flash', dur:0.14, a:0.70, col:'#FFF6E4'},
  descent:    {kind:'dark',  dur:0.30, a:0.70, col:'#2A0F14'},
  bridge:     {kind:'dark',  dur:0.40, a:0.95, col:'#000000'},
  burst:      {kind:'flash', dur:0.26, a:1.00, col:'#FFFBF0'},
  gliss:      {kind:'sweep', dur:0.28, a:1,    col:'#F3EADA'},
  finale:     {kind:'flash', dur:0.22, a:1.00, col:'#FFFBF0'},
  hush:       {kind:'dark',  dur:0.34, a:0.92, col:'#0B0507'},
  choir:      {kind:'flash', dur:0.20, a:0.80, col:'#FFE9BE'},
  curtain:    {kind:'flash', dur:0.18, a:0.90, col:'#FFF6E4'},
};
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

  // Per-section camera: a slow drift or push, plus a beat punch. Locked-off frames
  // read as dead; this is the cheapest production value in the whole build.
  const CAM={};
  SECTIONS.forEach((sec,i)=>{
    const r=mulberry32(1000+i*37);
    const kind=r();
    CAM[sec.id]= kind<0.34 ? {z0:1.005,z1:1.075,px:0,py:0}            // push in
              : kind<0.62 ? {z0:1.075,z1:1.010,px:0,py:0}             // pull out
              : kind<0.82 ? {z0:1.045,z1:1.045,px:(r()-0.5)*0.055,py:(r()-0.5)*0.022} // lateral drift
              :             {z0:1.015,z1:1.055,px:(r()-0.5)*0.030,py:-0.015};
  });

  function drawFrame(t){
    const E=env(t);
    x.save(); x.globalCompositeOperation='source-over'; x.globalAlpha=1;
    x.fillStyle=PAL.night; x.fillRect(0,0,W,H); x.restore();
    const C=CAM[E.sec.id]||{z0:1.02,z1:1.02,px:0,py:0};
    const u=smoothstep(0,1,E.sp);
    const punch = E.beatPulse*0.010*(0.4+E.bands.rms*0.9);
    const z = C.z0+(C.z1-C.z0)*u + punch;
    const dx = C.px*W*(u-0.5)*2 + noise2(t*0.23,3.1)*W*0.0022;
    const dy = C.py*H*(u-0.5)*2 + noise2(t*0.19,8.7)*H*0.0022;
    x.save();
    x.translate(W/2+dx,H/2+dy); x.scale(z,z); x.translate(-W/2,-H/2);
    const fn=SCENES[E.sec.scene];
    if(fn) fn(x,W,H,E); else x.drawImage(paper,0,0);
    x.restore();

    // --- section transition punctuation ---
    // Cuts land on section boundaries, which sit on musical events; a short flash or
    // sweep stops 24 hard cuts from reading as a slideshow.
    const since=t-E.sec.t0;
    const TR=TRANS[E.sec.id];
    if(TR && since<TR.dur){
      const k=1-since/TR.dur;
      x.save();
      if(TR.kind==='flash'){
        x.globalCompositeOperation='screen'; x.globalAlpha=Math.pow(k,1.5)*TR.a;
        x.fillStyle=TR.col; x.fillRect(0,0,W,H);
      } else if(TR.kind==='dark'){
        x.globalCompositeOperation='multiply'; x.globalAlpha=Math.pow(k,1.3)*TR.a;
        x.fillStyle=TR.col; x.fillRect(0,0,W,H);
      } else if(TR.kind==='sweep'){
        // a sheet of paper pulled across the frame
        const u=1-k;
        x.globalAlpha=1; x.fillStyle=TR.col;
        x.fillRect(W*ease2(u),0,W,H);
        x.globalAlpha=0.5; x.fillStyle='#00000022';
        x.fillRect(W*ease2(u)-W*0.012,0,W*0.012,H);
      }
      x.restore();
    }

    // grain boil at 15fps, and the deckled paper edge
    x.save(); x.globalCompositeOperation='overlay'; x.globalAlpha=0.40;
    x.drawImage(grains[Math.floor(E.f/2)%grains.length],0,0); x.restore();
    deckle(x,W,H,{inset:0,amp:Math.round(W*0.0045),col:PAL.paper});
    return c;
  }
  return {drawFrame,canvas:c,ctx:x,env,LINES};
}
