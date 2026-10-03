// Tonal system. Three grounds give the song its arc:
//   PAPER  bright cream, ink figure        — the charming opening
//   NIGHT  true dark, cream/gold ornament, LIGHT figure — the villain emerging
//   BLAZE  saturated gold, ink figure      — the spectacle
import {PAL,rgba,mix} from './palette.mjs';
import {clamp} from './noise.mjs';

export const TONE={
  paper:{ ground:'paper', fig:PAL.ink,   ink:PAL.ink,   orn:PAL.terra,     text:PAL.ink,
          accent:PAL.terra, rim:null,                       vig:0.30, vigCol:'#1a120c'},
  night:{ ground:'night', fig:'#F0E2CC', ink:PAL.paper, orn:PAL.goldPale,  text:PAL.paper,
          accent:PAL.pink,  rim:rgba('#FFE6B8',0.55),       vig:0.62, vigCol:'#000000'},
  blaze:{ ground:'blaze', fig:PAL.ink,   ink:PAL.ink,   orn:PAL.ink,       text:PAL.ink,
          accent:PAL.ox,    rim:null,                       vig:0.34, vigCol:'#2a1406'},
};

// Paint the base field. `mix01` cross-fades toward the next tone for transitions.
export function ground(x,W,H,E,name,{heat=0}={}){
  if(name==='night'){
    const g=x.createLinearGradient(0,0,0,H);
    g.addColorStop(0,'#140A0D'); g.addColorStop(0.55,'#1C0E12'); g.addColorStop(1,'#0C0607');
    x.fillStyle=g; x.fillRect(0,0,W,H);
    // the paper is still there, just barely — keeps the stock in the image
    x.save(); x.globalCompositeOperation='overlay'; x.globalAlpha=0.16;
    x.drawImage(E.paper,0,0); x.restore();
    return;
  }
  if(name==='blaze'){
    x.drawImage(E.paper,0,0);
    x.save(); x.globalCompositeOperation='multiply'; x.globalAlpha=0.55+heat*0.25;
    const g=x.createRadialGradient(W/2,H*0.44,0,W/2,H*0.5,W*0.78);
    g.addColorStop(0,'#FFE9A8'); g.addColorStop(0.45,'#F2C45E'); g.addColorStop(1,'#C98A3C');
    x.fillStyle=g; x.fillRect(0,0,W,H); x.restore();
    return;
  }
  x.drawImage(E.paper,0,0);
}

export function vignette(x,W,H,T,extra=0){
  const g=x.createRadialGradient(W/2,H*0.46,H*0.20,W/2,H*0.5,H*1.08);
  g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,rgba(T.vigCol,clamp(T.vig+extra,0,1)));
  x.save(); x.fillStyle=g; x.fillRect(0,0,W,H); x.restore();
}

// Legibility plate behind text on busy grounds.
export function plate(x,W,H,{y,h,col='#000000',a=0.28,feather=true}={}){
  x.save(); x.globalAlpha=a;
  if(feather){
    const g=x.createLinearGradient(0,y-h*0.6,0,y+h*0.6);
    g.addColorStop(0,rgba(col,0)); g.addColorStop(0.5,rgba(col,1)); g.addColorStop(1,rgba(col,0));
    x.fillStyle=g;
  } else x.fillStyle=col;
  x.fillRect(0,y-h*0.6,W,h*1.2); x.restore();
}
