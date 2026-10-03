// Distinct Deco backdrop treatments so no two sections look alike.
import {PAL,rgba,mix} from './palette.mjs';
import {rays,arcBands,halftone,chevrons,ziggurat} from './ink.mjs';
import {noise2,fbm,clamp,smoothstep,mulberry32} from './noise.mjs';
const TAU=Math.PI*2;

// 1. SUNBURST — use sparingly; it's the loudest card in the deck.
export function bgRays(x,W,H,E,{a=0.34,n=26,rot=0,col=PAL.goldPale,r1=null,cy=0.46}={}){
  rays(x,W/2,H*cy,W*0.05,r1??W*0.80,n,{col,a,rot,duty:0.46});
}

// 2. SKYLINE — stepped ziggurat city, the signature Deco silhouette.
export function bgSkyline(x,W,H,E,{a=0.26,col=PAL.ink,base=0.80,seed=5,scale=1}={}){
  const r=mulberry32(seed);
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  let px=-W*0.06;
  while(px<W*1.06){
    const w=W*(0.040+r()*0.070)*scale;
    const h=H*(0.10+r()*0.36)*scale;
    const kind=r();
    const yB=H*base;
    if(kind<0.42){
      // ziggurat setbacks — the Deco skyscraper
      const steps=3+((r()*3)|0);
      for(let s2=0;s2<steps;s2++){
        const t=s2/steps;
        const ww=w*(1-t*0.58), hh=h*(0.34+t*0.66);
        x.fillRect(px+(w-ww)/2, yB-hh, ww, hh);
      }
      x.fillRect(px+w*0.455, yB-h*1.16, w*0.09, h*0.22);              // spire
      x.beginPath(); x.arc(px+w*0.5, yB-h*1.16, w*0.055,0,TAU); x.fill();
    } else if(kind<0.70){
      // chamfered tower with a crown of fins
      x.beginPath();
      x.moveTo(px,yB); x.lineTo(px,yB-h*0.86);
      x.lineTo(px+w*0.22,yB-h); x.lineTo(px+w*0.78,yB-h);
      x.lineTo(px+w,yB-h*0.86); x.lineTo(px+w,yB);
      x.closePath(); x.fill();
      for(let f=0;f<4;f++) x.fillRect(px+w*(0.18+f*0.2), yB-h*1.12, w*0.055, h*0.14);
    } else {
      // low block with a stepped parapet
      x.fillRect(px, yB-h*0.62, w, h*0.62);
      for(let f=0;f<5;f++) x.fillRect(px+w*(f*0.2), yB-h*0.70, w*0.12, h*0.09);
    }
    px+=w*(1.02+r()*0.10);
  }
  x.restore();
}

// 3. SCALLOP / FAN TILE — the classic 1920s fan pattern.
export function bgScallop(x,W,H,E,{a=0.20,col=PAL.terra,r=null,rows=7,phase=0}={}){
  const R=Math.max(8, r??W*0.085);
  x.save(); x.globalAlpha=a; x.strokeStyle=col; x.lineWidth=W*0.0022;
  for(let j=-1;j<rows+1;j++){
    const y=j*R*0.62+H*0.02;
    const off=(j%2)?R*0.5:0;
    for(let i=-1;i<Math.ceil(W/R)+1;i++){
      const cx=i*R+off+phase;
      for(let k=1;k<=3;k++){
        x.beginPath(); x.arc(cx,y,R*k/3.2,Math.PI*0.02,Math.PI*0.98); x.stroke();
      }
    }
  }
  x.restore();
}

// 4. BANDS — broad horizontal colour bars, poster-flat.
export function bgBands(x,W,H,E,{cols=[PAL.paperDeep,PAL.paper],a=1,n=9,skew=0}={}){
  x.save(); x.globalAlpha=a;
  for(let i=0;i<n;i++){
    const y0=H*i/n, y1=H*(i+1)/n;
    x.fillStyle=cols[i%cols.length];
    x.beginPath(); x.moveTo(0,y0+skew*i); x.lineTo(W,y0-skew*i);
    x.lineTo(W,y1-skew*i); x.lineTo(0,y1+skew*i); x.closePath(); x.fill();
  }
  x.restore();
}

// 5. GRID — the machine. Perfect, cold, accelerating.
export function bgGrid(x,W,H,E,{a=0.22,col=PAL.ink,n=18,persp=0.55,phase=0}={}){
  x.save(); x.globalAlpha=a; x.strokeStyle=col; x.lineWidth=W*0.0015;
  const hz=H*persp;
  for(let i=0;i<=n;i++){
    const u=i/n;
    x.beginPath(); x.moveTo(u*W,H); x.lineTo(W*0.5+(u-0.5)*W*0.16, hz); x.stroke();
  }
  for(let k=1;k<26;k++){
    const t=((k+phase%1)/26); const y=hz+(H-hz)*Math.pow(t,2.1);
    x.beginPath(); x.moveTo(0,y); x.lineTo(W,y); x.stroke();
  }
  x.restore();
}

// 6. COLUMNS — a Deco colonnade.
export function bgColumns(x,W,H,E,{a=0.20,col=PAL.ink,n=7,top=0.10,bot=0.82}={}){
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  for(let i=0;i<n;i++){
    const cx=W*(i+0.5)/n, w=W*0.030;
    x.fillRect(cx-w/2,H*top,w,H*(bot-top));
    for(let k=0;k<4;k++) x.fillRect(cx-w*(0.9-k*0.14),H*top-H*0.016*(k+1),w*(1.8-k*0.28),H*0.013);
    x.fillRect(cx-w*1.1,H*bot,w*2.2,H*0.018);
  }
  x.restore();
}

// 7. MOIRE — concentric rings, hypnotic.
export function bgMoire(x,W,H,E,{a=0.16,col=PAL.ink,n=34,cy=0.46,step=null,phase=0}={}){
  const st=step??W*0.019;
  x.save(); x.globalAlpha=a; x.strokeStyle=col; x.lineWidth=W*0.0022;
  for(let i=1;i<=n;i++){x.beginPath();x.arc(W/2,H*cy,i*st+phase,0,TAU);x.stroke();}
  x.restore();
}

// 8. CHEVRON FIELD — big zig-zags, graphic and loud.
export function bgChevron(x,W,H,E,{a=0.16,col=PAL.ink,rows=8,n=10,amp=null,phase=0}={}){
  const A=amp??H*0.055;
  x.save(); x.globalAlpha=a; x.strokeStyle=col; x.lineWidth=W*0.006; x.lineJoin='miter';
  for(let j=-1;j<rows+1;j++){
    const y=j*(H/rows)+phase%(H/rows);
    x.beginPath();
    for(let i=0;i<=n;i++) x.lineTo(i/n*W, y+((i%2)?A:-A));
    x.stroke();
  }
  x.restore();
}

// 9. DRAPE — soft vertical folds, for intimate moments.
export function bgDrape(x,W,H,E,{a=1,col=PAL.ox,folds=16}={}){
  x.save(); x.globalAlpha=a;
  for(let i=0;i<folds;i++){
    const u=i/folds, u2=(i+1)/folds;
    const sh=0.52+0.48*Math.abs(Math.sin(i*1.37));
    x.fillStyle=mix(col,'#000000',0.50*(1-sh));
    x.fillRect(u*W,0,(u2-u)*W+1,H);
  }
  x.restore();
}

// 10. STARBURST TILE — small repeating Claude marks, wallpaper.
export function bgMarks(x,W,H,E,{a=0.12,col=PAL.terra,n=7,rot=0,r=null}={}){
  const R=Math.max(4, r??W*0.030);
  x.save();
  for(let j=0;j<n;j++)for(let i=0;i<Math.ceil(W/(R*3.2))+1;i++){
    const cx=i*R*3.2+((j%2)?R*1.6:0), cy=H*(j+0.5)/n;
    rays(x,cx,cy,R*0.26,R,11,{col,a,rot:rot+j*0.2,duty:0.42});
  }
  x.restore();
}
