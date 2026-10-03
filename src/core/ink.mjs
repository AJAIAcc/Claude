// Printed-ink primitives: misregistration, plate bleed, halftone screens, Deco ornament.
import {noise2,fbm,clamp} from './noise.mjs';
import {PAL,rgba} from './palette.mjs';

// Jitter a polyline so edges read as hand-cut lino / letterpress rather than vector-perfect.
export function wobble(pts,amp=1.6,f=0.05,ph=0){
  return pts.map(([x,y],i)=>[x+noise2(x*f+ph,y*f)*amp, y+noise2(x*f+99+ph,y*f+41)*amp]);
}
export function polyPath(x,pts,close=true){
  x.beginPath(); pts.forEach(([a,b],i)=>i?x.lineTo(a,b):x.moveTo(a,b)); if(close)x.closePath();
}

// Riso-style off-register printing: same art, small per-plate offsets, multiply blend.
export function plates(x,draw,layers){
  x.save(); x.globalCompositeOperation='multiply';
  for(const L of layers){
    x.save(); x.translate(L.dx||0,L.dy||0);
    x.globalAlpha=L.a==null?1:L.a; x.fillStyle=L.col; x.strokeStyle=L.col;
    draw(x,L); x.restore();
  }
  x.restore();
}

// Halftone dot screen clipped to the current path/rect. angle in rad.
export function halftone(x,X,Y,W,H,{col=PAL.ink,pitch=7,angle=Math.PI/5,amp=1,fn=null,a=1}={}){
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  const ca=Math.cos(angle),sa=Math.sin(angle);
  const R=Math.hypot(W,H), n=Math.ceil(R/pitch)+2;
  for(let j=-n;j<=n;j++)for(let i=-n;i<=n;i++){
    const px=X+W/2 + (i*pitch*ca - j*pitch*sa);
    const py=Y+H/2 + (i*pitch*sa + j*pitch*ca);
    if(px<X-pitch||px>X+W+pitch||py<Y-pitch||py>Y+H+pitch)continue;
    let t=amp;
    if(fn) t*=fn((px-X)/W,(py-Y)/H);
    if(t<=0.01)continue;
    const r=pitch*0.52*Math.sqrt(clamp(t,0,1));
    x.beginPath(); x.arc(px,py,r,0,6.2832); x.fill();
  }
  x.restore();
}

// Deco sunburst / ray fan.
export function rays(x,cx,cy,r0,r1,n,{col=PAL.gold,a=1,rot=0,duty=0.46,taper=true,wob=0}={}){
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  for(let i=0;i<n;i++){
    const t=i/n*Math.PI*2+rot, w=(Math.PI*2/n)*duty*0.5;
    const rr1 = r1*(1 + (wob? noise2(i*0.7,rot*2)*wob:0));
    x.beginPath();
    x.arc(cx,cy,r0,t-w*(taper?0.45:1),t+w*(taper?0.45:1));
    x.arc(cx,cy,rr1,t+w,t-w,true);
    x.closePath(); x.fill();
  }
  x.restore();
}

// Concentric Deco arc bands.
export function arcBands(x,cx,cy,rs,{col=PAL.ink,a=1,lw=5,a0=0,a1=Math.PI*2}={}){
  x.save(); x.globalAlpha=a; x.strokeStyle=col; x.lineWidth=lw; x.lineCap='butt';
  for(const r of rs){x.beginPath();x.arc(cx,cy,r,a0,a1);x.stroke();}
  x.restore();
}

// Chevron / zig-zag band — the signature Deco border.
export function chevrons(x,X,Y,W,H,{col=PAL.ink,a=1,n=14,lw=6,phase=0}={}){
  x.save();x.globalAlpha=a;x.strokeStyle=col;x.lineWidth=lw;x.lineJoin='miter';
  const step=W/n;
  x.beginPath();
  for(let i=0;i<=n;i++){const px=X+i*step; const py=Y+((i+phase)%2?H:0); i?x.lineTo(px,py):x.moveTo(px,py);}
  x.stroke();x.restore();
}

// Stepped Deco ziggurat frame
export function ziggurat(x,cx,cy,w,h,steps,{col=PAL.ink,a=1,lw=0,fill=true}={}){
  x.save();x.globalAlpha=a;x.fillStyle=col;x.strokeStyle=col;x.lineWidth=lw||3;
  for(let s=0;s<steps;s++){
    const t=s/steps, ww=w*(1-t*0.82), hh=h*(0.16+t*0.0);
    const y=cy+h*0.5-(s+1)*(h/steps);
    x.beginPath();x.rect(cx-ww/2,y,ww,h/steps*0.92);
    fill?x.fill():x.stroke();
  }
  x.restore();
}

// Ink-bled text: a soft spread pass under a crisp pass.
export function inkText(x,txt,px,py,{font,col=PAL.ink,align='left',base='alphabetic',
  bleed=0.16,spread=2.0,a=1,track=0}={}){
  x.save(); x.font=font; x.textAlign=track?'left':align; x.textBaseline=base; x.globalAlpha=a;
  const drawOne=(dx,dy,al,c)=>{
    x.globalAlpha=a*al; x.fillStyle=c;
    if(track){
      // manual letter-spacing
      let w=0; for(const ch of txt) w+=x.measureText(ch).width+track; w-=track;
      let sx = align==='center'? px-w/2 : align==='right'? px-w : px;
      for(const ch of txt){ x.fillText(ch,sx+dx,py+dy); sx+=x.measureText(ch).width+track; }
    } else x.fillText(txt,px+dx,py+dy);
  };
  if(bleed>0){
    for(const [dx,dy] of [[spread,0],[-spread,0],[0,spread],[0,-spread],[spread*0.7,spread*0.7],[-spread*0.7,-spread*0.7]])
      drawOne(dx,dy,bleed*0.5,col);
  }
  drawOne(0,0,1,col);
  x.restore();
}

export function measure(x,txt,font,track=0){
  x.save();x.font=font;let w=0;
  if(track){for(const ch of txt)w+=x.measureText(ch).width+track;w-=track;}
  else w=x.measureText(txt).width;
  x.restore();return w;
}
