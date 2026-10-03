// The theatre: proscenium arch, curtains, footlights, spotlight pools.
import {PAL,rgba,mix} from './palette.mjs';
import {rays,arcBands,halftone,chevrons} from './ink.mjs';
import {noise2,fbm,clamp,smoothstep} from './noise.mjs';

// Stepped Art-Deco proscenium. Returns the inner opening rect for content.
export function proscenium(x,W,H,{col=PAL.ink,a=1,steps=4,openW=0.70,openH=0.80,
  archR=0.26,thick=0.052,glow=null}={}){
  const ow=W*openW, oh=H*openH;
  const ox=(W-ow)/2, oy=H*0.055;
  x.save(); x.globalAlpha=a;
  // outer mass = whole frame minus the arch opening (even-odd)
  x.fillStyle=col; x.beginPath();
  x.rect(0,0,W,H);
  // opening path: rounded-top arch with stepped shoulders
  const r=ow*archR;
  x.moveTo(ox,oy+oh);
  x.lineTo(ox,oy+r);
  x.quadraticCurveTo(ox,oy, ox+r, oy);
  x.lineTo(ox+ow-r,oy);
  x.quadraticCurveTo(ox+ow,oy, ox+ow, oy+r);
  x.lineTo(ox+ow,oy+oh);
  x.closePath();
  x.fill('evenodd');
  x.restore();
  // stepped inner trim
  x.save(); x.globalAlpha=a*0.92; x.strokeStyle=col;
  for(let s=1;s<=steps;s++){
    const g=s*W*thick*0.30;
    x.lineWidth=Math.max(2,W*0.0032*(1+s*0.1));
    x.globalAlpha=a*(0.5-s*0.09);
    const rr=r+g;
    x.beginPath();
    x.moveTo(ox-g,oy+oh);
    x.lineTo(ox-g,oy-g+rr);
    x.quadraticCurveTo(ox-g,oy-g, ox-g+rr, oy-g);
    x.lineTo(ox+ow+g-rr,oy-g);
    x.quadraticCurveTo(ox+ow+g,oy-g, ox+ow+g, oy-g+rr);
    x.lineTo(ox+ow+g,oy+oh);
    x.stroke();
  }
  x.restore();
  return {x:ox,y:oy,w:ow,h:oh,r};
}

export function clipArch(x,o){
  x.beginPath();
  x.moveTo(o.x,o.y+o.h);
  x.lineTo(o.x,o.y+o.r);
  x.quadraticCurveTo(o.x,o.y,o.x+o.r,o.y);
  x.lineTo(o.x+o.w-o.r,o.y);
  x.quadraticCurveTo(o.x+o.w,o.y,o.x+o.w,o.y+o.r);
  x.lineTo(o.x+o.w,o.y+o.h);
  x.closePath(); x.clip();
}

// Heavy stage curtain with Deco swags. side: -1 left, +1 right. open: 0..1
export function curtain(x,W,H,side,open,{col=PAL.ox,a=1,folds=9}={}){
  const w=W*0.46*(1-open*0.92);
  if(w<4)return;
  x.save(); x.globalAlpha=a;
  const X0= side<0? 0 : W-w;
  for(let i=0;i<folds;i++){
    const t=i/folds, t2=(i+1)/folds;
    const fx0=X0+w*t, fx1=X0+w*t2;
    const sh=0.55+0.45*Math.abs(Math.sin((i+ (side<0?0:0.5))*1.7));
    x.fillStyle=mix(col,'#000000',0.42*(1-sh));
    x.beginPath();
    x.moveTo(fx0,0); x.lineTo(fx1,0);
    const belly=H*(0.52+0.10*Math.sin(i*2.1+side));
    x.quadraticCurveTo((fx0+fx1)/2+ (side<0?18:-18), belly, fx1, H);
    x.lineTo(fx0,H);
    x.quadraticCurveTo((fx0+fx1)/2, belly, fx0, 0);
    x.closePath(); x.fill();
  }
  x.restore();
}

// Footlight wash from the bottom edge.
export function footlights(x,W,H,{col=PAL.goldPale,a=0.5,n=11,reach=0.42}={}){
  x.save(); x.globalCompositeOperation='screen'; x.globalAlpha=a;
  for(let i=0;i<n;i++){
    const px=W*(i+0.5)/n;
    const g=x.createRadialGradient(px,H,0,px,H,H*reach);
    g.addColorStop(0,rgba(col,0.55)); g.addColorStop(1,rgba(col,0));
    x.fillStyle=g; x.beginPath(); x.arc(px,H,H*reach,Math.PI,0); x.fill();
  }
  x.restore();
}

// Hard spotlight cone from above + elliptical floor pool.
export function spotlight(x,W,H,cx,cy,r,{col='#FFF3DC',a=0.5,cone=true,from=-0.12}={}){
  x.save();
  if(cone){
    x.globalCompositeOperation='screen'; x.globalAlpha=a*0.5;
    const g=x.createLinearGradient(cx,H*from,cx,cy+r*0.4);
    g.addColorStop(0,rgba(col,0.55)); g.addColorStop(1,rgba(col,0.02));
    x.fillStyle=g; x.beginPath();
    x.moveTo(cx-r*0.17,H*from); x.lineTo(cx+r*0.17,H*from);
    x.lineTo(cx+r*1.08,cy+r*0.42); x.lineTo(cx-r*1.08,cy+r*0.42);
    x.closePath(); x.fill();
  }
  x.globalCompositeOperation='screen'; x.globalAlpha=a;
  const g2=x.createRadialGradient(cx,cy,0,cx,cy,r);
  g2.addColorStop(0,rgba(col,0.8)); g2.addColorStop(0.55,rgba(col,0.22)); g2.addColorStop(1,rgba(col,0));
  x.fillStyle=g2; x.beginPath(); x.ellipse(cx,cy,r,r*0.62,0,0,6.2832); x.fill();
  x.restore();
}
