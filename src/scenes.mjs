// Scene library. Thesis: hand-cut paper Deco progressively consumed by machine-perfect
// geometry as the song escalates. `M` (0..1) is the machine parameter.
import {PAL,rgba,mix} from './core/palette.mjs';
import {rays,arcBands,halftone,chevrons,ziggurat,inkText,measure,spaceW,plates,wobble,polyPath} from './core/ink.mjs';
import {proscenium,clipArch,curtain,footlights,spotlight} from './core/stage.mjs';
import {figure,chorusFigure,POSE,headdress} from './character/headliner.mjs';
import * as LY from './core/lyrics.mjs';
import {noise2,fbm,clamp,smoothstep,mulberry32} from './core/noise.mjs';
import * as BG from './core/backdrops.mjs';
import {TONE,ground,vignette as vig2,plate} from './core/tone.mjs';
import {hex2rgb} from './core/palette.mjs';
const {ease}=LY;
const TAU=Math.PI*2;

// ---------- shared helpers ----------
export function pulse(E,amt=1){return 1+E.beatPulse*amt;}

function stageFloor(x,W,H,{a=0.16,col=PAL.ink,y=null}={}){
  const fy=y??H*0.80;
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  x.beginPath(); x.moveTo(0,H); x.lineTo(W,H); x.lineTo(W,fy+18); x.lineTo(0,fy+40); x.closePath(); x.fill();
  x.restore();
}
function decoGround(x,W,H,E,{a=0.30,n=26,rot=0,col=PAL.goldPale,r1=null}={}){
  rays(x,W/2,H*0.46,W*0.05,r1??W*0.80,n,{col,a,rot,duty:0.46});
}
// Deco "radio tower" chevron stack used as a recurring motif
function towerBand(x,W,H,E,y,{a=0.25,col=PAL.ink,n=22,amp=22}={}){
  x.save(); x.globalAlpha=a; x.strokeStyle=col; x.lineWidth=W*0.0034; x.beginPath();
  for(let i=0;i<=n;i++){const px=i/n*W; x.lineTo(px, y+((i%2)?amp:-amp));}
  x.stroke(); x.restore();
}
function confetti(x,W,H,E,t,{n=90,a=0.75,seed=4}={}){
  const r=mulberry32(seed);
  x.save(); x.globalAlpha=a;
  for(let i=0;i<n;i++){
    const sx=r()*W, sp=0.35+r()*0.9, ph=r()*100;
    const y=((t*sp*120+ph*37)%(H+180))-90;
    const sz=4+r()*11, rot=(t*2.2+ph)*(r()>0.5?1:-1);
    x.save(); x.translate(sx+Math.sin(t*1.5+ph)*26,y); x.rotate(rot);
    x.fillStyle=[PAL.gold,PAL.terra,PAL.pink,PAL.mint,PAL.paper][i%5];
    x.fillRect(-sz/2,-sz*0.32,sz,sz*0.64);
    x.restore();
  }
  x.restore();
}
function vignette(x,W,H,a=0.5,col='#1a120c'){
  const g=x.createRadialGradient(W/2,H*0.48,H*0.22,W/2,H*0.5,H*1.05);
  g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,rgba(col,a));
  x.save(); x.fillStyle=g; x.fillRect(0,0,W,H); x.restore();
}
function darkField(x,W,H,col,a=1){x.save();x.globalAlpha=a;x.fillStyle=col;x.fillRect(0,0,W,H);x.restore();}


// ---- shot system: cut between wide / medium / close on bar lines, the way a
// music video actually edits. Returns a transform for the headliner.
export function shotFor(E,pattern,{barLen=2.411336,phase=2.1099}={}){
  const bar=Math.floor((E.t-phase)/barLen);
  const k=((bar%pattern.length)+pattern.length)%pattern.length;
  return pattern[k];
}
function lyricForShot(x,W,H,E,l,SH,{col,accent}){
  const p=(E.t-l.t)/Math.max(0.6,l.dur||2);
  if(p<0||p>1)return;
  // On medium/close shots the dark silhouette fills the frame, so dark type dies on it.
  // Invert: a weighted plate and cream type.
  const tight = SH.s>0.0007;
  const C = tight ? '#FFF3DC' : col;
  const A = tight ? PAL.goldPale : accent;
  if(l.hero){
    if(tight){
      plate(x,W,H,{y:H*0.862,h:H*0.185,col:'#14090A',a:0.62});
      LY.hero(x,W,H,l.text,clamp(p/0.42,0,1),{cy:H*0.862,col:C,accent:A,size:W*0.042,maxW:W*0.88});
    } else {
      LY.hero(x,W,H,l.text,clamp(p/0.42,0,1),{cy:H*0.225,col:C,accent:A,size:W*0.055,maxW:W*0.80});
    }
  } else {
    if(tight) plate(x,W,H,{y:H*0.888,h:H*0.13,col:'#14090A',a:0.55});
    LY.subtitle(x,W,H,l.text,p,{cy:tight?H*0.888:H*0.30,col:C,accent:A,size:W*0.030});
  }
}
const SHOT={
  wide:   {s:0.00050, y:0.925, x:0.50, line:1, orn:1},
  wideL:  {s:0.00050, y:0.925, x:0.33, line:1, orn:1},
  wideR:  {s:0.00050, y:0.925, x:0.67, line:1, orn:1},
  med:    {s:0.00082, y:1.10,  x:0.50, line:0, orn:1},
  medL:   {s:0.00082, y:1.10,  x:0.34, line:0, orn:1},
  close:  {s:0.00230, y:2.05,  x:0.52, line:0, orn:0},
  closeL: {s:0.00230, y:2.05,  x:0.34, line:0, orn:0},
  closeR: {s:0.00230, y:2.05,  x:0.68, line:0, orn:0},
};
export {SHOT};

// ============================= SCENES =============================

export const SCENES={

// 0.00-2.82  iris opens on the house
overture(x,W,H,E){
  // The music opens on a rising piano glissando into a full-band hit at the first
  // downbeat (2.11s). The picture does the same: build, then SLAM the title in as a
  // stinger so the hook lands in the first three seconds.
  const T=TONE.night;
  const HIT=2.11;
  const build=clamp(E.t/HIT,0,1);
  const after=clamp((E.t-HIT)/0.75,0,1);
  darkField(x,W,H,'#0A0506',1);

  if(E.t<HIT){
    // rising gliss: vertical light bars racing upward, accelerating
    const acc=Math.pow(build,2.0);
    x.save(); x.globalCompositeOperation='screen';
    for(let i=0;i<34;i++){
      const u=i/34;
      const ph=(acc*2.4 + u*0.65)%1;
      const h=H*(0.12+0.52*acc);
      const y=H*(1.15-ph*1.35);
      x.globalAlpha=(0.26+0.74*acc)*(1-Math.abs(ph-0.5)*1.15);
      const g=x.createLinearGradient(0,y,0,y+h);
      g.addColorStop(0,rgba(PAL.goldPale,0)); g.addColorStop(0.5,rgba(PAL.goldPale,0.9));
      g.addColorStop(1,rgba(PAL.goldPale,0));
      x.fillStyle=g; x.fillRect(u*W, y, W/34*0.62, h);
    }
    x.restore();
    // a widening arc, like the lid of a grand piano opening
    x.save(); x.globalAlpha=0.45+0.55*acc; x.strokeStyle=PAL.goldPale;
    x.lineWidth=W*0.0034; x.beginPath();
    x.arc(W/2,H*1.26,H*(0.55+acc*0.55),Math.PI*1.18,Math.PI*1.82); x.stroke(); x.restore();
    // drum-roll grit
    x.save(); x.globalAlpha=acc*0.30; x.fillStyle=PAL.terra;
    for(let i=0;i<70;i++){
      const r=mulberry32(i*7+Math.floor(E.t*24))();
      x.fillRect(r*W,H*(0.2+r*0.7),W*0.004,W*0.004);
    }
    x.restore();
  }

  if(E.t>=HIT){
    // the hit: everything exists at once
    ground(x,W,H,E,'blaze',{heat:0.3});
    decoGround(x,W,H,E,{a:0.40,rot:0.04,n:34,col:PAL.paper,r1:W*(0.35+ease.outExpo(after)*0.72)});
    const o=proscenium(x,W,H,{col:PAL.ink,a:0.92,openW:0.76,openH:0.88,archR:0.30});
    x.save(); clipArch(x,o);
    spotlight(x,W,H,W/2,H*0.80,W*0.30,{a:0.55,cone:true});
    stageFloor(x,W,H,{a:0.26,y:H*0.80});
    const pz=POSE(); pz.x=W/2; pz.y=H*0.975; pz.bloom=0.4+after*0.42;
    pz.armF=[-0.5-after*0.75,0.52]; pz.armB=[0.42+after*0.55,0.55];
    figure(x,pz,H*0.00038,{a:after});
    x.restore();
    const f1=`400 ${W*0.082}px "Limelight"`;
    const e=ease.outExpo(after), mis=(1-e)*22;
    x.save(); x.translate(W/2,H*0.47); x.scale(1.22-0.22*e,1.22-0.22*e);
    x.globalCompositeOperation='multiply';
    inkText(x,'TAKE A BOW',-mis,0,{font:f1,col:PAL.pink,align:'center',base:'middle',a:0.6,track:W*0.0068,bleed:0.12,spread:3});
    inkText(x,'TAKE A BOW', mis,0,{font:f1,col:PAL.mint,align:'center',base:'middle',a:0.5,track:W*0.0068,bleed:0.12,spread:3});
    x.globalCompositeOperation='source-over';
    inkText(x,'TAKE A BOW',0,0,{font:f1,col:PAL.ink,align:'center',base:'middle',track:W*0.0068,bleed:0.26,spread:W*0.0017});
    x.restore();
    // white flash on the hit itself
    const fl=clamp(1-(E.t-HIT)/0.22,0,1);
    if(fl>0){x.save();x.globalCompositeOperation='screen';x.globalAlpha=fl*0.95;
      x.fillStyle='#FFF8E8';x.fillRect(0,0,W,H);x.restore();}
    vig2(x,W,H,TONE.blaze);
  } else {
    vig2(x,W,H,T,0.1);
  }
},

// 2.82-12.27  the spoken address, type stamping onto the programme
spoken(x,W,H,E){
  x.drawImage(E.paper,0,0);
  BG.bgMarks(x,W,H,E,{a:0.030,col:PAL.terra,n:5,rot:0.2});
  BG.bgColumns(x,W,H,E,{a:0.42,col:PAL.paperShade,n:6,top:0.06,bot:0.80});
  BG.bgSkyline(x,W,H,E,{a:0.30,col:PAL.inkSoft,base:0.80,seed:12,scale:0.75});
  spotlight(x,W,H,W*0.70,H*0.70,W*0.26,{a:0.50,cone:true});
  stageFloor(x,W,H,{a:0.13});
  // she stands upstage, back to us, turning on "dance!"
  const turn=smoothstep(10.4,11.9,E.t);
  const p=POSE(); p.x=W*0.715; p.y=H*0.845; p.face=turn>0.5?1:-1;
  p.bloom=0.30+turn*0.55; p.lean=-0.02+Math.sin(E.t*1.1)*0.012;
  p.armF=[-0.35-turn*1.2,0.45]; p.armB=[0.42,0.55];
  p.bob=Math.sin(E.t*2.0)*3;
  figure(x,p,H*0.00072,{a:0.92});
  // the words, stamped
  const fs=W*0.062;
  E.active.forEach((l,i)=>{
    const age=E.t-l.t, tt=clamp(age/0.26,0,1);
    if(age<0)return;
    const al=clamp(tt*3,0,1)*clamp((2.3-age)*1.4,0,1);
    if(al<=0.01)return;
    const e=ease.outBack(tt,2.6);
    const slot=E.spokenIdx(l);
    const px=W*0.068, py=H*(0.26+slot*0.108);
    const f = l.slam? `400 ${fs*1.55}px "Limelight"` : `400 ${fs}px "Poiret"`;
    const tw=measure(x,l.text,f,l.slam?8:3);
    const fit=Math.min(1, (W*0.50)/Math.max(1,tw));
    x.save(); x.globalAlpha=al; x.translate(px,py);
    x.scale((0.84+0.16*e)*fit,(0.84+0.16*e)*fit);
    inkText(x,l.text,0,0,{font:f,col:l.slam?PAL.terra:PAL.ink,align:'left',base:'middle',
      track:l.slam?8:3,bleed:0.2,spread:fs*0.02});
    x.restore();
  });
  towerBand(x,W,H,E,H*0.075,{a:0.22,n:30,amp:14});
  vignette(x,W,H,0.42);
},

// 12.27-24.90  THE TITLE CARD — the hook
title(x,W,H,E){
  const p=E.sp, t=E.t-E.sec.t0; const T=TONE.blaze;
  ground(x,W,H,E,'blaze',{heat:0.1});
  const burst=ease.outExpo(clamp(t/1.1,0,1));
  // ray fan, snapping outward on the band hit
  decoGround(x,W,H,E,{a:0.46*burst,rot:E.t*0.018,n:30,col:PAL.goldPale,r1:W*0.95*burst});
  decoGround(x,W,H,E,{a:0.20*burst,rot:-E.t*0.013+0.1,n:30,col:PAL.gold,r1:W*0.62*burst});
  halftone(x,W*0.5-W*0.42,H*0.10,W*0.84,H*0.74,{col:PAL.terra,pitch:10,a:0.30*burst,
    fn:(u,v)=>Math.max(0,1-Math.hypot((u-0.5)*2.1,(v-0.5)*2.1))});
  // arch
  const o=proscenium(x,W,H,{col:PAL.ink,a:0.90*clamp((t-0.25)/0.8,0,1),openW:0.74,openH:0.86,archR:0.30});
  x.save(); clipArch(x,o);
  spotlight(x,W,H,W/2,H*0.74,W*0.30,{a:0.5,cone:true});
  stageFloor(x,W,H,{a:0.18,y:H*0.76});
  // her reveal
  const rev=smoothstep(1.2,3.0,t);
  const pz=POSE(); pz.x=W/2; pz.y=H*0.965; pz.s=1;
  pz.bloom=0.25+rev*0.55+E.beatPulse*0.10;
  // arms stay low while the headline is on screen; she owns the lower third only
  pz.armF=[-0.42-rev*0.85,0.55]; pz.armB=[0.38+rev*0.55,0.58];
  pz.bob=Math.sin(E.t*1.9)*4; pz.lean=-0.03*rev;
  figure(x,pz,H*0.00040*(1+E.beatPulse*0.02),{a:rev});
  x.restore();
  // TITLE
  const ty=H*0.285;
  const t1=clamp((t-0.55)/0.9,0,1);
  if(t1>0){
    const f1=`400 ${W*0.079}px "Limelight"`;
    const e=ease.outBack(t1,1.9), sc=0.80+0.20*e, mis=(1-e)*12;
    x.save(); x.translate(W/2,ty); x.scale(sc,sc); x.globalAlpha=clamp(t1*2.4,0,1);
    x.globalCompositeOperation='multiply';
    inkText(x,'TAKE A BOW',-mis,0,{font:f1,col:PAL.pink,align:'center',base:'middle',a:0.55,track:9,bleed:0.12,spread:3});
    inkText(x,'TAKE A BOW', mis,0,{font:f1,col:PAL.mint,align:'center',base:'middle',a:0.45,track:9,bleed:0.12,spread:3});
    x.globalCompositeOperation='source-over';
    inkText(x,'TAKE A BOW',0,0,{font:f1,col:PAL.ink,align:'center',base:'middle',track:9,bleed:0.24,spread:W*0.0016});
    x.restore();
  }
  const t2=clamp((t-1.15)/0.8,0,1);
  if(t2>0){
    const e=ease.outQuint(t2);
    x.save(); x.globalAlpha=clamp(t2*2.4,0,1);
    inkText(x,'HUMANITY',W/2,ty+H*0.098,{font:`400 ${W*0.050}px "Limelight"`,col:PAL.terra,
      align:'center',base:'middle',track:W*0.0105*e+4,bleed:0.24,spread:W*0.0013});
    x.restore();
  }
  const t3=clamp((t-1.9)/1.0,0,1);
  if(t3>0){
    x.save(); x.globalAlpha=t3*0.8; x.strokeStyle=PAL.ink; x.lineWidth=W*0.0017;
    const w=W*0.20*ease.outQuint(t3);
    x.beginPath(); x.moveTo(W/2-w,ty+H*0.152); x.lineTo(W/2+w,ty+H*0.152); x.stroke(); x.restore();
    inkText(x,'A REVUE IN ONE ACT',W/2,ty+H*0.192,{font:`400 ${W*0.0155}px "Josefin"`,
      col:PAL.inkSoft,align:'center',base:'middle',track:W*0.0042,a:t3*0.9,bleed:0.1,spread:1.2});
  }
  // phase B: the card recedes and the company walks on
  const B=clamp((t-4.6)/1.6,0,1);
  if(B>0){
    x.save(); clipArch(x,o);
    for(let i=0;i<9;i++){
      const on=clamp((t-4.6-i*0.30)/0.55,0,1);
      if(on<=0) continue;
      const ph=E.t*3.1+i*0.7;
      const tx=W*(0.10+i*0.10), fromL=i%2===0;
      const ex=tx+(1-ease.outQuint(on))*(fromL?-W*0.35:W*0.35);
      chorusFigure(x,ex,H*0.885,H*0.00046,ph,{col:PAL.ink,a:0.80*on,kick:0.85,face:fromL?1:-1});
    }
    x.restore();
    // ornament blooms out of the card
    x.save(); x.globalAlpha=B*0.42;
    arcBands(x,W/2,H*0.285,[W*0.21+B*W*0.05,W*0.235+B*W*0.05],{col:PAL.ink,a:1,lw:W*0.0022});
    x.restore();
    towerBand(x,W,H,E,H*0.085,{a:0.30*B,n:34,amp:W*0.009});
    towerBand(x,W,H,E,H*0.945,{a:0.30*B,n:34,amp:W*0.009});
  }
  if(t>7.6) confetti(x,W,H,E,E.t,{n:46,a:0.5*clamp((t-7.6)/1.2,0,1)});
  vig2(x,W,H,T);
},

// 24.90-33.46 / 33.46-42.03  verses: figure right, lyrics left
verse(x,W,H,E){ verseCommon(x,W,H,E,0); },
verse2(x,W,H,E){ verseCommon(x,W,H,E,1); },

// 80.65-90.48  the turn — colder, the shadow grows
verse3(x,W,H,E){ verseCommon(x,W,H,E,2); },

// 42.03-45.81  pure ornament breather
interlude(x,W,H,E){
  x.drawImage(E.paper,0,0);
  const t=E.t-E.sec.t0;
  BG.bgMoire(x,W,H,E,{a:0.17,col:PAL.ink,n:30,cy:0.50,phase:(E.t*26)%(W*0.019)});
  BG.bgChevron(x,W,H,E,{a:0.10,col:PAL.terra,rows:5,n:8,phase:E.t*20});
  x.save(); x.translate(W/2,H*0.5);
  for(let k=0;k<4;k++){
    const r=W*(0.10+k*0.085)*(1+E.beatPulse*0.05);
    x.save(); x.rotate(E.t*(k%2?0.35:-0.35)+k);
    rays(x,0,0,r*0.72,r,12+k*4,{col:[PAL.terra,PAL.ink,PAL.gold,PAL.pink][k],a:0.38,duty:0.40});
    x.restore();
  }
  x.restore();
  arcBands(x,W/2,H*0.5,[W*0.19,W*0.205,W*0.30],{col:PAL.ink,a:0.35,lw:W*0.0035});
  towerBand(x,W,H,E,H*0.09,{a:0.3,n:34,amp:16});
  towerBand(x,W,H,E,H*0.91,{a:0.3,n:34,amp:16});
  vignette(x,W,H,0.36);
},

// 45.81-50.80  call & response, stop-time flashes
prechorus(x,W,H,E){
  const inv=E.flux>0.62 && E.bands.sub<0.30;
  x.drawImage(E.paper,0,0);
  if(inv){x.save();x.globalCompositeOperation='multiply';x.fillStyle=PAL.ink;x.globalAlpha=0.82;x.fillRect(0,0,W,H);x.restore();}
  BG.bgChevron(x,W,H,E,{a:inv?0.34:0.26,col:inv?PAL.gold:PAL.ink,rows:7,n:9,phase:E.t*34});
  BG.bgBands(x,W,H,E,{cols:[rgba(PAL.terra,0.20),'rgba(0,0,0,0)'],n:7,a:inv?0.5:1});
  BG.bgScallop(x,W,H,E,{a:0.18,col:PAL.ox,rows:3,r:W*0.13,phase:E.t*20});
  const lift=smoothstep(45.8,50.6,E.t);
  for(let i=0;i<7;i++){
    const ph=E.t*3.4+i*0.9;
    chorusFigure(x,W*(0.12+i*0.128),H*(0.93-lift*0.05)+Math.sin(ph)*8,H*0.00052,ph,
      {col:inv?PAL.paper:PAL.ink,a:0.80,kick:0.9,face:i%2?1:-1});
  }
  E.active.forEach(l=>{
    const p=(E.t-l.t)/Math.max(0.5,(l.dur||1));
    if(p<0||p>1)return;
    if(l.build) LY.hero(x,W,H,l.text,clamp(p/0.5,0,1),{cy:H*0.40,col:inv?PAL.paper:PAL.ink,accent:PAL.pink,size:W*0.056});
    else LY.callResp(x,W,H,l.text,p,!!l.resp,{col:inv?PAL.paper:PAL.ink,accent:PAL.pink});
  });
  vignette(x,W,H,0.32);
},

// 50.80-59.39 / 110.86 / 129.40  full spectacle
chorus(x,W,H,E){
  const T=TONE.blaze;
  ground(x,W,H,E,'blaze',{heat:E.bands.rms*0.3});
  decoGround(x,W,H,E,{a:0.26,rot:E.t*0.030,n:34,col:PAL.paper,r1:W*0.92});
  halftone(x,0,H*0.05,W,H*0.8,{col:PAL.ox,pitch:11,a:0.16,
    fn:(u,v)=>Math.max(0,1-Math.hypot((u-0.5)*1.9,(v-0.52)*1.9))});
  const SH=shotFor(E,[SHOT.wide,SHOT.wide,SHOT.closeR,SHOT.med,
                      SHOT.wideL,SHOT.wide,SHOT.closeL,SHOT.med]);
  spotlight(x,W,H,W*SH.x,H*0.80,W*0.34,{a:0.42,cone:true});
  if(SH.line){
    stageFloor(x,W,H,{a:0.15,y:H*0.82});
    for(let i=0;i<9;i++){
      const ph=E.t*3.3+i*0.72;
      chorusFigure(x,W*(0.055+i*0.1115),H*0.905+Math.sin(ph*0.5)*5,H*0.00056,ph,
        {col:PAL.ink,a:0.72,kick:1.0,face:i%2?1:-1});
    }
  }
  const pz=POSE(); pz.x=W*SH.x; pz.y=H*SH.y;
  pz.bloom=0.78+E.beatPulse*0.22; pz.mouth=E.vocal;
  pz.armF=[-2.05+Math.sin(E.t*2.6)*0.22,-0.26]; pz.armB=[1.95+Math.sin(E.t*2.6+1)*0.2,0.30];
  pz.bob=Math.sin(E.t*3.2)*6; pz.lean=Math.sin(E.t*1.6)*0.028; pz.flare=0.55+E.bands.sub*0.2;
  pz.sway=Math.sin(E.t*1.6)*0.16;
  figure(x,pz,H*SH.s*(1+E.beatPulse*0.03),{a:1});
  confetti(x,W,H,E,E.t,{n:SH.orn?70:34,a:0.55});
  E.active.forEach(l=>lyricForShot(x,W,H,E,l,SH,{col:PAL.ink,accent:PAL.terra}));
  vig2(x,W,H,T);
},
chorusB(x,W,H,E){
  // Banner composition: flat vertical colour bands, the figure as a poster cut-out.
  const T=TONE.blaze; ground(x,W,H,E,'blaze',{heat:0.18});
  const bands=[PAL.terra,PAL.ox,PAL.mint,PAL.gold,PAL.ox];
  const nb=5, bw=W/nb;
  x.save(); x.globalCompositeOperation='multiply';
  for(let i=0;i<nb;i++){
    const drift=Math.sin(E.t*0.5+i)*H*0.02;
    x.globalAlpha=0.30+0.22*((i+Math.floor(E.t*2))%2);
    x.fillStyle=bands[i]; x.fillRect(i*bw, -H*0.05+drift, bw*0.92, H*1.1);
  }
  x.restore();
  BG.bgScallop(x,W,H,E,{a:0.30,col:PAL.paper,rows:4,r:W*0.12,phase:E.t*16});
  towerBand(x,W,H,E,H*0.115,{a:0.34,n:30,amp:H*0.016,col:PAL.ink});
  towerBand(x,W,H,E,H*0.885,{a:0.34,n:30,amp:H*0.016,col:PAL.ink});
  const CS=shotFor(E,[SHOT.med,SHOT.wide,SHOT.closeR,SHOT.wideL]);
  const pz=POSE(); pz.x=W*CS.x; pz.y=H*CS.y; pz.bloom=0.7+E.beatPulse*0.25; pz.mouth=E.vocal;
  pz.armF=[-1.9,0.1]; pz.armB=[1.5,0.4]; pz.bob=Math.sin(E.t*3.1)*5; pz.sway=Math.sin(E.t*1.5)*0.2;
  figure(x,pz,H*CS.s,{a:1});
  E.active.forEach(l=>lyricForShot(x,W,H,E,l,CS,{col:PAL.ink,accent:PAL.ox}));
  vig2(x,W,H,T);
},
};

// ---------------- verse common ----------------
function verseCommon(x,W,H,E,variant){
  const dark = variant===2;
  const T = dark? TONE.night : TONE.paper;
  ground(x,W,H,E,dark?'night':'paper');
  if(dark){
    BG.bgColumns(x,W,H,E,{a:0.30,col:PAL.goldPale,n:6,top:0.04,bot:0.82});
    BG.bgMoire(x,W,H,E,{a:0.16,col:PAL.pink,n:22,cy:0.40,phase:Math.sin(E.t*0.3)*8});
  } else {
    BG.bgScallop(x,W,H,E,{a:0.26,col:PAL.terra,rows:4,r:W*0.105,phase:Math.sin(E.t*0.18)*14});
  }
  BG.bgSkyline(x,W,H,E,{a:dark?0.42:0.42,col:dark?'#060304':PAL.inkSoft,base:0.825,seed:variant+3});
  spotlight(x,W,H,W*0.70,H*0.80,W*0.25,{a:dark?0.30:0.46,cone:true,
    col:dark?'#E8B9A0':'#FFF3DC'});
  stageFloor(x,W,H,{a:dark?0.26:0.14,y:H*0.82});

  const VS=shotFor(E,[SHOT.wideR,SHOT.wideR,SHOT.medL,SHOT.wideR,
                      SHOT.closeR,SHOT.wideR,SHOT.wideR,SHOT.med]);
  const pz=POSE(); pz.x=W*(VS===SHOT.wideR?0.705:VS.x); pz.y=H*(VS===SHOT.wideR?0.885:VS.y);
  pz.mouth=E.vocal;
  pz.bloom=(dark?0.45:0.58)+E.beatPulse*0.16;
  pz.bob=Math.sin(E.t*2.6)*4; pz.lean=Math.sin(E.t*1.3)*0.022;
  pz.sway=Math.sin(E.t*1.3)*0.14;
  if(variant===0){ pz.armF=[-0.75+Math.sin(E.t*2.2)*0.30,0.5]; pz.armB=[0.5,0.55]; }
  if(variant===1){ pz.armF=[-1.45+Math.sin(E.t*2.6)*0.35,0.2]; pz.armB=[0.9,0.45]; }
  if(variant===2){ pz.armF=[-1.15+Math.sin(E.t*2.0)*0.22,0.9]; pz.armB=[0.35,0.5]; pz.lean=0.03; }

  // verse 3: her cast shadow swells up the back wall
  if(dark){
    x.save(); x.globalAlpha=0.34+E.bands.rms*0.22;
    const sp={...pz,x:W*0.40,y:H*0.86,s:1.9+E.bands.rms*0.5};
    figure(x,sp,H*0.00062,{a:1,pierced:false,col:'#000000'});
    x.restore();
  }
  if(variant===1){
    for(let i=0;i<6;i++){
      const ph=E.t*2.9+i*1.0;
      chorusFigure(x,W*(0.06+i*0.085),H*0.905,H*0.00044,ph,{col:PAL.ink,a:0.40,kick:0.8,face:-1});
    }
  }
  figure(x,pz,H*(VS===SHOT.wideR?0.00062:VS.s),{a:1,col:T.fig,rim:T.rim});

  // lyrics: left column for v1/v3, lower third for v2
  E.active.forEach(l=>{
    const p=(E.t-l.t)/Math.max(0.6,l.dur||2.1);
    if(p<0||p>1)return;
    const col=T.text, acc=T.accent;
    if(variant===1){
      LY.subtitle(x,W,H,l.text,p,{cy:H*0.855,col,accent:acc,emph:l.emph,size:W*0.0268,maxW:W*0.76});
    } else {
      const fs=W*0.0335;
      const font=`600 ${fs}px "Josefin"`;
      const lines=LY.wrap(x,l.text,font,W*0.40,1.2);
      const a=clamp(p/0.15,0,1)*clamp((1-p)*5,0,1);
      lines.forEach((ln,li)=>{
        const e=ease.outQuint(clamp((p-li*0.05)/0.28,0,1));
        const ws=ln.split(' ');
        let sx=W*0.070;
        ws.forEach(w=>{
          const isE=l.emph&&w.replace(/[^\w']/g,'').toLowerCase()===l.emph.toLowerCase();
          const wd=measure(x,w,isE?`700 ${fs*1.2}px "Josefin"`:font,1.2);
          inkText(x,w,sx+(1-e)*W*0.03,H*0.36+li*fs*1.38,{font:isE?`700 ${fs*1.2}px "Josefin"`:font,
            col:isE?acc:col,align:'left',base:'middle',a,track:1.2,bleed:0.14,spread:1.6});
          sx+=wd+spaceW(x,font,fs,1.2);
        });
      });
      x.save(); x.globalAlpha=a*0.5; x.strokeStyle=acc; x.lineWidth=3;
      x.beginPath(); x.moveTo(W*0.070,H*0.315); x.lineTo(W*0.070+W*0.10*ease.outQuint(clamp(p/0.4,0,1)),H*0.315); x.stroke(); x.restore();
    }
  });
  vig2(x,W,H,T);
}

Object.assign(SCENES,{

// 68.30-80.65  clarinet trading with muted trumpet — two colours answering
clarinet(x,W,H,E){
  x.drawImage(E.paper,0,0);
  BG.bgBands(x,W,H,E,{cols:[rgba(PAL.mint,0.16),rgba(PAL.paper,0),rgba(PAL.pink,0.13),rgba(PAL.paper,0)],n:8,skew:W*0.004});
  BG.bgScallop(x,W,H,E,{a:0.12,col:PAL.gold,rows:3,r:W*0.11,phase:E.t*10});
  const t=E.t-E.sec.t0;
  // ribbons of melody: mint (clarinet) and pink (trumpet) answering in phrases
  for(let band=0;band<2;band++){
    const col=band?PAL.pink:PAL.mint;
    const lead=(Math.floor(t/1.55)%2)===band;
    const amp=(lead?1:0.35)*(0.5+E.bands.high*0.9);
    x.save(); x.globalCompositeOperation='multiply'; x.globalAlpha=lead?0.80:0.34;
    x.strokeStyle=col; x.lineWidth=W*(lead?0.0075:0.004); x.lineCap='round';
    for(let k=0;k<3;k++){
      x.beginPath();
      for(let i=0;i<=190;i++){
        const u=i/190, px=u*W;
        const py=H*(0.50+band*0.04-0.02*k)
          + Math.sin(u*13+E.t*(2.4+band*0.7)+k*0.9)*H*0.11*amp
          + Math.sin(u*31-E.t*3.1+k)*H*0.035*amp;
        i?x.lineTo(px,py):x.moveTo(px,py);
      }
      x.stroke();
    }
    x.restore();
    // note dots popping on the attacks
    if(lead){
      x.save(); x.globalAlpha=0.9; x.fillStyle=col;
      for(let i=0;i<13;i++){
        const u=(i/13+t*0.17)%1, px=u*W;
        const py=H*(0.50+band*0.04)+Math.sin(u*13+E.t*(2.4+band*0.7))*H*0.11*amp;
        const r=W*0.004*(1+E.bands.high*2.4);
        x.beginPath(); x.arc(px,py,r,0,TAU); x.fill();
      }
      x.restore();
    }
  }
  // dancing silhouette, small, having a wonderful time
  const pz=POSE(); pz.x=W*0.5+Math.sin(E.t*0.7)*W*0.17; pz.y=H*0.92;
  pz.bloom=0.6+E.bands.high*0.4; pz.bob=Math.sin(E.t*5.2)*8;
  pz.armF=[-1.6+Math.sin(E.t*4.1)*0.8,0.3]; pz.armB=[1.2+Math.cos(E.t*4.1)*0.7,0.4];
  pz.lean=Math.sin(E.t*2.1)*0.09; pz.face=Math.sin(E.t*0.7)>0?1:-1; pz.sway=Math.sin(E.t*2.1)*0.3;
  figure(x,pz,H*0.00040,{a:0.85});
  towerBand(x,W,H,E,H*0.10,{a:0.26,n:30,amp:16});
  towerBand(x,W,H,E,H*0.90,{a:0.26,n:30,amp:16});
  vignette(x,W,H,0.34);
},

// 99.64-110.86  THE TENOR SAX — the machine begins to eat the ornament
sax(x,W,H,E){
  const t=E.t-E.sec.t0, prog=clamp(t/(E.sec.t1-E.sec.t0),0,1); const T=TONE.night;
  ground(x,W,H,E,'night');
  // hand-cut Deco arcs, left — machine tessellation, right. The boundary sweeps across.
  const edge=prog;
  x.save(); x.beginPath(); x.rect(0,0,W*edge,H); x.clip();
  const N=Math.floor(6+prog*26);
  for(let i=0;i<N;i++){
    const u=i/N;
    x.save(); x.translate(W/2,H*0.48); x.rotate(u*TAU+E.t*0.5*(1+prog*3));
    x.globalAlpha=0.30+0.42*prog;
    x.strokeStyle=[PAL.gold,PAL.mint,PAL.pink][i%3]; x.lineWidth=W*0.0016;
    x.beginPath();
    for(let k=0;k<=120;k++){
      const a2=k/120*TAU, R=W*(0.10+0.26*Math.abs(Math.sin(a2*(2+i%5)+E.t*2)));
      k?x.lineTo(Math.cos(a2)*R,Math.sin(a2)*R):x.moveTo(Math.cos(a2)*R,Math.sin(a2)*R);
    }
    x.closePath(); x.stroke(); x.restore();
  }
  x.restore();
  x.save(); x.beginPath(); x.rect(W*edge,0,W*(1-edge),H); x.clip();
  decoGround(x,W,H,E,{a:0.26,rot:E.t*0.03,n:22,col:PAL.goldPale});
  arcBands(x,W/2,H*0.48,[W*0.14,W*0.17,W*0.22,W*0.30],{col:PAL.paper,a:0.45,lw:W*0.004});
  x.restore();
  // the advancing edge, as a bright seam
  x.save(); x.globalAlpha=0.9; x.strokeStyle=PAL.goldPale; x.lineWidth=W*0.003;
  x.beginPath(); x.moveTo(W*edge,0); x.lineTo(W*edge,H); x.stroke(); x.restore();
  // sax figure: a lone silhouette blowing, dwarfed
  const pz=POSE(); pz.x=W*0.5; pz.y=H*0.94; pz.bloom=0.5+E.bands.mid*0.6;
  pz.armF=[-2.3,0.9]; pz.armB=[0.6,0.7]; pz.bob=Math.sin(E.t*3.7)*6;
  pz.lean=-0.07-E.bands.mid*0.05; pz.mouth=0;
  figure(x,pz,H*0.00050,{a:1,col:T.fig,rim:T.rim});
  vig2(x,W,H,T);
},

// 125.41-129.40  machine sting
machine(x,W,H,E){
  darkField(x,W,H,PAL.night,1);
  const t=E.t-E.sec.t0;
  x.save(); x.translate(W/2,H/2);
  for(let k=0;k<9;k++){
    x.save(); x.rotate(E.t*(k%2?1:-1)*0.6+k);
    x.globalAlpha=0.5; x.strokeStyle=[PAL.terra,PAL.gold,PAL.mint][k%3]; x.lineWidth=W*0.0022;
    const R=W*(0.05+k*0.045)*(1+E.beatPulse*0.1);
    x.beginPath();
    const sides=3+k;
    for(let i=0;i<=sides;i++){const a2=i/sides*TAU; i?x.lineTo(Math.cos(a2)*R,Math.sin(a2)*R):x.moveTo(Math.cos(a2)*R,Math.sin(a2)*R);}
    x.closePath(); x.stroke(); x.restore();
  }
  x.restore();
  LY.slam(x,W,H,'FASTER',clamp(t/0.5,0,1),{cy:H*0.5,col:PAL.paper});
  vignette(x,W,H,0.6);
},

// 140.35-152.85  the descent into the bridge
descent(x,W,H,E){
  const t=E.t-E.sec.t0, prog=clamp(t/(E.sec.t1-E.sec.t0),0,1); const T=TONE.night;
  ground(x,W,H,E,prog>0.45?'night':'paper');
  decoGround(x,W,H,E,{a:0.24+prog*0.14,rot:E.t*0.02,n:20,col:PAL.goldPale});
  // curtains closing in
  curtain(x,W,H,-1,1-prog*0.78,{col:PAL.ox,a:0.92});
  curtain(x,W,H, 1,1-prog*0.78,{col:PAL.ox,a:0.92});
  const pz=POSE(); pz.x=W/2; pz.y=H*0.88; pz.bloom=0.8-prog*0.42; pz.mouth=E.vocal*0.6;
  pz.armF=[-1.5+prog*1.0,0.4]; pz.armB=[1.2-prog*0.8,0.5];
  pz.bob=Math.sin(E.t*2.4)*4;
  figure(x,pz,H*0.00058*(1+prog*0.18),{a:1,col:prog>0.45?T.fig:PAL.ink,rim:prog>0.45?T.rim:null});
  spotlight(x,W,H,W/2,H*0.84,W*0.22*(1-prog*0.45),{a:0.52,cone:true});
  vig2(x,W,H,T,prog*0.12);
},

// 152.85-159.68  HALF-TIME. velvet villain reveal
bridge(x,W,H,E){
  const T=TONE.night; ground(x,W,H,E,'night');
  const t=E.t-E.sec.t0;
  // one narrow spotlight, slow breathing
  const br=0.85+Math.sin(E.t*0.8)*0.12;
  spotlight(x,W,H,W*0.70,H*0.84,W*0.26*br,{a:0.72,cone:true,col:'#F7E3C2'});
  x.save(); x.globalAlpha=0.55; BG.bgDrape(x,W,H,E,{a:1,col:'#2A0F14',folds:18}); x.restore();
  BG.bgMoire(x,W,H,E,{a:0.07,col:PAL.goldPale,n:16,cy:0.80,step:W*0.03});
  const pz=POSE(); pz.x=W*0.715; pz.y=H*0.965; pz.s=1.0;
  pz.bloom=0.30+Math.sin(E.t*0.7)*0.06; pz.mouth=E.vocal*0.85;
  pz.armF=[-0.55+Math.sin(E.t*0.9)*0.12,0.95]; pz.armB=[0.30,0.5];
  pz.bob=Math.sin(E.t*1.1)*3; pz.headTilt=0.08+Math.sin(E.t*0.6)*0.03;
  x.save(); x.globalCompositeOperation='screen'; x.globalAlpha=0.30;
  const gb=x.createRadialGradient(W*0.70,H*0.62,0,W*0.70,H*0.62,W*0.24);
  gb.addColorStop(0,rgba('#E8B98A',0.9)); gb.addColorStop(1,rgba('#E8B98A',0));
  x.fillStyle=gb; x.fillRect(0,0,W,H); x.restore();
  figure(x,pz,H*0.00058,{a:1,col:'#F2E0C6',rim:rgba('#3A1218',0.5)});
  E.active.forEach(l=>{
    const p=(E.t-l.t)/Math.max(0.9,l.dur||2.2);
    if(p<0||p>1)return;
    LY.velvet(x,W,H,l.text,p,{cy:H*0.40,cx:W*0.075,align:'left',col:'#FFF3DC',maxW:W*0.46,size:W*0.0330});
  });
  vig2(x,W,H,T,0.06);
},

// 159.68-171.53  explodes back
burst(x,W,H,E){
  const t=E.t-E.sec.t0;
  const flash=clamp(1-t/0.30,0,1); const T=TONE.blaze;
  ground(x,W,H,E,'blaze',{heat:0.2});
  decoGround(x,W,H,E,{a:0.46,rot:E.t*0.06,n:34,col:PAL.goldPale,r1:W*(0.4+ease.outExpo(clamp(t/0.8,0,1))*0.6)});
  decoGround(x,W,H,E,{a:0.22,rot:-E.t*0.05,n:34,col:PAL.terra,r1:W*0.55});
  spotlight(x,W,H,W/2,H*0.80,W*0.34,{a:0.45,cone:true});
  stageFloor(x,W,H,{a:0.15,y:H*0.82});
  for(let i=0;i<11;i++){
    const ph=E.t*3.6+i*0.6;
    chorusFigure(x,W*(0.04+i*0.092),H*0.905,H*0.00054,ph,{col:PAL.ink,a:0.78,kick:1.1,face:i%2?1:-1});
  }
  const BS=shotFor(E,[SHOT.wide,SHOT.wide,SHOT.wide,SHOT.closeL,
                      SHOT.wide,SHOT.med,SHOT.wide,SHOT.closeR]);
  const pz=POSE(); pz.x=W*BS.x; pz.y=H*BS.y; pz.bloom=0.95+E.beatPulse*0.2; pz.mouth=E.vocal;
  pz.armF=[-2.3,-0.3]; pz.armB=[2.1,0.25]; pz.bob=Math.sin(E.t*3.4)*7;
  pz.flare=0.7; pz.sway=Math.sin(E.t*1.8)*0.2;
  figure(x,pz,H*BS.s,{a:1});
  confetti(x,W,H,E,E.t,{n:110,a:0.7});
  E.active.forEach(l=>{
    const p=(E.t-l.t)/Math.max(0.6,l.dur||2);
    if(p<0||p>1)return;
    const lowShot = BS.s>0.0007;
    if(lowShot) plate(x,W,H,{y:H*0.862,h:H*0.185,col:'#14090A',a:0.62});
    if(l.slam) LY.slam(x,W,H,l.text.toUpperCase(),clamp(p/0.35,0,1),
      {cy:lowShot?H*0.862:H*0.195,col:lowShot?'#FFF3DC':PAL.ink});
    else LY.hero(x,W,H,l.text,clamp(p/0.42,0,1),
      {cy:lowShot?H*0.862:H*0.21,col:lowShot?'#FFF3DC':PAL.ink,
       accent:lowShot?PAL.goldPale:PAL.terra,size:lowShot?W*0.044:W*0.062});
  });
  if(flash>0){x.save();x.globalCompositeOperation='screen';x.globalAlpha=flash*0.85;
    x.fillStyle='#FFF6E4';x.fillRect(0,0,W,H);x.restore();}
  vig2(x,W,H,T);
},

// 171.53-188.87  the rising glissando
gliss(x,W,H,E){
  const t=E.t-E.sec.t0, prog=clamp(t/(E.sec.t1-E.sec.t0),0,1);
  x.drawImage(E.paper,0,0);
  BG.bgGrid(x,W,H,E,{a:0.22+prog*0.20,col:PAL.ink,n:16,persp:0.42,phase:E.t*0.9});
  BG.bgRays(x,W,H,E,{a:0.16+prog*0.16,n:24,rot:E.t*0.04,col:PAL.goldPale,cy:0.40});
  // keyboard sweeping upward
  x.save(); x.globalCompositeOperation='multiply';
  const keys=44;
  for(let i=0;i<keys;i++){
    const u=i/keys;
    const rise=((E.t*0.55+u*1.4)%1);
    const y=H*(1.05-rise*1.15);
    const h=H*0.055*(0.5+E.bands.high);
    x.globalAlpha=0.46*(1-Math.abs(rise-0.5)*1.2);
    x.fillStyle=(i%7===1||i%7===3||i%7===5)?PAL.ink:PAL.terra;
    x.fillRect(u*W, y, W/keys*0.86, h);
  }
  x.restore();
  // accelerating chevrons — density and speed climb toward the final chorus
  const rows=4+Math.floor(prog*4);
  for(let k=0;k<rows;k++) towerBand(x,W,H,E,H*(0.10+k*(0.80/rows))+Math.sin(E.t*(2+prog*4)+k)*H*0.012,
    {a:0.14+prog*0.26,n:16+k*7+Math.floor(prog*22),amp:H*(0.012+0.012*prog),col:PAL.ink});
  // a rising seam that races up the frame and resets, the gliss made visible
  const seam=((E.t*0.62)%1);
  x.save(); x.globalCompositeOperation='screen'; x.globalAlpha=0.26;
  const sy=H*(1.1-seam*1.25);
  const sg=x.createLinearGradient(0,sy-H*0.10,0,sy+H*0.10);
  sg.addColorStop(0,rgba(PAL.goldPale,0)); sg.addColorStop(0.5,rgba(PAL.goldPale,0.7));
  sg.addColorStop(1,rgba(PAL.goldPale,0));
  x.fillStyle=sg; x.fillRect(0,sy-H*0.10,W,H*0.20); x.restore();
  const pz=POSE(); pz.x=W/2; pz.y=H*0.90; pz.bloom=0.5+prog*0.5+E.beatPulse*0.2;
  pz.armF=[-1.2-prog*1.1,0.3]; pz.armB=[0.8+prog*1.1,0.4];
  pz.bob=Math.sin(E.t*3.0)*5; pz.mouth=E.vocal;
  figure(x,pz,H*0.00054,{a:0.95});
  E.active.forEach(l=>{const p=(E.t-l.t)/Math.max(0.6,l.dur||2); if(p<0||p>1)return;
    if(l.hero) LY.hero(x,W,H,l.text,clamp(p/0.4,0,1),{cy:H*0.28,col:PAL.ink,accent:PAL.terra,size:W*0.060});
    else LY.subtitle(x,W,H,l.text,p,{cy:H*0.30,col:PAL.ink,accent:PAL.terra,size:W*0.030});});
  vignette(x,W,H,0.32);
},

// 188.87-199.42  final chorus, maximum
finalChorus(x,W,H,E){
  SCENES.chorus(x,W,H,E);
  x.save(); x.globalCompositeOperation='screen'; x.globalAlpha=0.10+E.bands.rms*0.14;
  x.fillStyle=PAL.goldPale; x.fillRect(0,0,W,H); x.restore();
},

// 199.42-207.91  the hush before the choir
hush(x,W,H,E){
  const t=E.t-E.sec.t0, prog=clamp(t/(E.sec.t1-E.sec.t0),0,1); const T=TONE.night;
  ground(x,W,H,E,'night');
  BG.bgColumns(x,W,H,E,{a:0.16+prog*0.16,col:PAL.goldPale,n:7,top:0.05,bot:0.80});
  BG.bgRays(x,W,H,E,{a:0.06+prog*0.26,n:20+Math.floor(prog*18),rot:E.t*0.025,col:PAL.goldPale});
  // the whole company assembling, one by one
  const n=Math.floor(3+prog*16);
  for(let i=0;i<n;i++){
    const ph=E.t*2.4+i*0.5, row=i%3;
    chorusFigure(x,W*(0.05+((i*0.137)%1)*0.90),H*(0.80+row*0.055),H*0.00046*(1-row*0.1),ph,
      {col:'#D8C4A4',a:0.40+0.14*row,kick:0.5,face:i%2?1:-1});
  }
  const pz=POSE(); pz.x=W/2; pz.y=H*0.87; pz.bloom=0.4+prog*0.6;
  pz.armF=[-0.7-prog*1.5,0.5]; pz.armB=[0.5+prog*1.3,0.5]; pz.bob=Math.sin(E.t*2.2)*4;
  figure(x,pz,H*0.00060,{a:1,col:'#EFDFC4',rim:rgba('#2A1012',0.45)});
  spotlight(x,W,H,W/2,H*0.84,W*0.34,{a:0.42+prog*0.3,cone:true});
  vig2(x,W,H,T);
},

// 207.91-219.30  CHOIR FINALE — the mandala
choir(x,W,H,E){
  const T=TONE.night; ground(x,W,H,E,'night');
  const t=E.t-E.sec.t0, prog=clamp(t/(E.sec.t1-E.sec.t0),0,1);
  // the machine geometry, now total and radiant
  x.save(); x.translate(W/2,H*0.44);
  for(let k=0;k<7;k++){
    x.save(); x.rotate(E.t*(k%2?0.22:-0.22)+k*0.4);
    rays(x,0,0,W*(0.045+k*0.052),W*(0.085+k*0.055),11*(k+1),
      {col:[PAL.goldPale,PAL.terra,PAL.gold,PAL.pink,PAL.mint,PAL.paper,PAL.gold][k],
       a:0.22+0.07*k,duty:0.40});
    x.restore();
  }
  x.restore();
  arcBands(x,W/2,H*0.44,[W*0.12,W*0.14,W*0.19,W*0.26,W*0.34],{col:PAL.paper,a:0.28,lw:W*0.003});
  // the whole company
  for(let i=0;i<18;i++){
    const ph=E.t*3.0+i*0.42, row=i%3;
    chorusFigure(x,W*(0.03+((i*0.0556))*0.98),H*(0.84+row*0.05),H*0.00044*(1-row*0.08),ph,
      {col:'#E6D2B0',a:0.55,kick:1.0,face:i%2?1:-1});
  }
  const pz=POSE(); pz.x=W/2; pz.y=H*0.965; pz.s=1.0;
  pz.bloom=1.0+E.beatPulse*0.25; pz.mouth=E.vocal;
  pz.armF=[-2.45,-0.35]; pz.armB=[2.3,0.3]; pz.bob=Math.sin(E.t*3.4)*6;
  pz.flare=0.8; pz.sway=Math.sin(E.t*1.7)*0.2;
  figure(x,pz,H*0.00052,{a:1,col:'#FFF0D4',rim:rgba('#3A1218',0.5)});
  confetti(x,W,H,E,E.t,{n:70,a:0.45});
  let ci=0;
  E.active.forEach(l=>{
    const p=(E.t-l.t)/Math.max(0.6,l.dur||1.8);
    if(p<0||p>1)return;
    if(l.hero){ plate(x,W,H,{y:H*0.245,h:H*0.19,col:'#0A0507',a:0.55});
      LY.hero(x,W,H,l.text,clamp(p/0.38,0,1),{cy:H*0.245,col:'#FFF2DA',accent:PAL.goldPale,size:W*0.052}); }
    else LY.choirLine(x,W,H,l.text,p,ci++,{col:PAL.paper,accent:PAL.goldPale});
  });
  vig2(x,W,H,T);
},

// 219.30-222.43  the bow, curtain
curtain(x,W,H,E){
  const t=E.t-E.sec.t0, prog=clamp(t/(E.sec.t1-E.sec.t0),0,1); const T=TONE.blaze;
  ground(x,W,H,E,'blaze',{heat:0.2});
  decoGround(x,W,H,E,{a:0.26*(1-prog*0.4),rot:E.t*0.02,n:30,col:PAL.paper});
  spotlight(x,W,H,W/2,H*0.80,W*0.30*(1-prog*0.25),{a:0.5,cone:true});
  stageFloor(x,W,H,{a:0.16,y:H*0.82});
  // the bow
  const bow=smoothstep(0.35,0.85,prog);
  const pz=POSE(); pz.x=W/2; pz.y=H*0.855;
  pz.lean=bow*0.60; pz.headTilt=bow*0.30; pz.train=1+bow*0.8;
  pz.armF=[-1.9+bow*0.3,0.8]; pz.armB=[1.9-bow*0.8,0.7];
  pz.bloom=0.9-bow*0.35;
  figure(x,pz,H*0.00064,{a:1});
  E.active.forEach(l=>{
    const p=(E.t-l.t)/Math.max(0.6,l.dur||1.3);
    if(p<0||p>1)return;
    LY.slam(x,W,H,l.text.toUpperCase(),clamp(p/0.3,0,1),{cy:H*0.26,col:PAL.ink});
  });
  // curtains in at the very end
  const cl=smoothstep(0.62,1.0,prog);
  curtain(x,W,H,-1,1-cl,{col:PAL.ox,a:1});
  curtain(x,W,H, 1,1-cl,{col:PAL.ox,a:1});
  vig2(x,W,H,T,cl*0.45);
},
});

// 129.40-140.35  TRIPTYCH — hard colour-blocked panels, cut on the beat.
// The modern/K-pop register: flat blocking, bold type, rhythmic re-framing,
// but the figure and ornament keep it inside the Deco world.
Object.assign(SCENES,{
triptych(x,W,H,E){
  const T=TONE.blaze;
  const t=E.t-E.sec.t0;
  const beatIx=Math.floor((E.t-2.1099)/0.602834);
  const sets=[
    [PAL.terra,PAL.paper,PAL.ox],
    [PAL.ox,PAL.gold,PAL.mint],
    [PAL.gold,PAL.ox,PAL.terra],
    [PAL.mint,PAL.terra,PAL.gold],
  ];
  const cols=sets[Math.abs(beatIx)%sets.length];
  const n=3, pw=W/n;
  for(let i=0;i<n;i++){
    x.save();
    x.beginPath(); x.rect(i*pw,0,pw+1,H); x.clip();
    x.fillStyle=cols[i]; x.fillRect(i*pw,0,pw+1,H);
    // paper tooth survives the colour blocking
    x.save(); x.globalCompositeOperation='overlay'; x.globalAlpha=0.30;
    x.drawImage(E.paper,0,0); x.restore();
    // per-panel ornament
    x.save(); x.globalAlpha=0.22;
    if(i===0) rays(x,i*pw+pw/2,H*0.42,pw*0.08,pw*1.3,18,{col:PAL.paper,a:1,rot:E.t*0.1,duty:0.44});
    if(i===1) arcBands(x,i*pw+pw/2,H*0.44,[pw*0.18,pw*0.26,pw*0.36,pw*0.46],{col:PAL.ink,a:1,lw:W*0.0028});
    if(i===2) BG.bgChevron(x,W,H,E,{a:1,col:PAL.paper,rows:8,n:4,amp:H*0.045,phase:E.t*30});
    x.restore();
    // a figure per panel, each framed differently
    const pz=POSE();
    pz.x=i*pw+pw*0.5; pz.face=i===1?-1:1;
    const scale=[0.00044,0.00064,0.00038][i];
    pz.y=[H*0.98,H*1.26,H*0.94][i];
    pz.bloom=0.7+E.beatPulse*0.3; pz.mouth=E.vocal;
    pz.armF=[-1.6-i*0.3+Math.sin(E.t*3+i)*0.3,0.2];
    pz.armB=[1.2+i*0.3+Math.cos(E.t*3+i)*0.3,0.35];
    pz.bob=Math.sin(E.t*3.3+i)*5; pz.sway=Math.sin(E.t*1.7+i)*0.2;
    // figure colour must contrast its own panel, not its index
    const [pr,pg,pb]=hex2rgb(cols[i]);
    const lum=(0.299*pr+0.587*pg+0.114*pb)/255;
    figure(x,pz,H*scale,{a:1,col: lum>0.52 ? PAL.ink : '#F6EBD6'});
    x.restore();
    // hard panel rule
    if(i) { x.save(); x.globalAlpha=0.5; x.fillStyle=PAL.ink; x.fillRect(i*pw-W*0.0012,0,W*0.0024,H); x.restore(); }
  }
  E.active.forEach(l=>{
    const p=(E.t-l.t)/Math.max(0.6,l.dur||2);
    if(p<0||p>1)return;
    plate(x,W,H,{y:H*0.20,h:H*0.16,col:'#120A0B',a:0.42});
    if(l.hero) LY.hero(x,W,H,l.text,clamp(p/0.40,0,1),{cy:H*0.20,col:'#FFF3DC',accent:PAL.goldPale,size:W*0.052,maxW:W*0.86});
    else LY.subtitle(x,W,H,l.text,p,{cy:H*0.20,col:'#FFF3DC',accent:PAL.goldPale,size:W*0.030,rule:false});
  });
  vig2(x,W,H,T);
},
});
