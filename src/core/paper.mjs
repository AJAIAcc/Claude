// Paper substrate: handmade stock, fibres, foxing, deckle edge + animated grain "boil".
import {createCanvas} from 'canvas';
import {fbm,noise2,mulberry32,clamp,smoothstep} from './noise.mjs';
import {PAL,hex2rgb} from './palette.mjs';

export function makePaper(W,H,{tint=PAL.paper,seed=7}={}){
  const c=createCanvas(W,H),x=c.getContext('2d');
  const img=x.createImageData(W,H),d=img.data;
  const [br,bg,bb]=hex2rgb(tint);
  const rnd=mulberry32(seed);
  const S=1/260, FS=1/3.2;
  for(let j=0;j<H;j++){
    for(let i=0;i<W;i++){
      const o=(j*W+i)*4;
      // broad mottling of the stock
      let v = fbm(i*S, j*S, 5)*0.5;
      // long fibres, mostly horizontal, a few diagonal
      const fib = noise2(i*FS*0.08, j*FS*2.3)*0.5 + noise2(i*FS*2.1, j*FS*0.07)*0.28;
      v += fib*0.085;
      // fine tooth
      v += (rnd()-0.5)*0.055;
      // foxing: sparse warm age-spots
      const fx = fbm(i*0.0045+31.7, j*0.0045-12.3, 3);
      const fox = smoothstep(0.26,0.50,fx)*smoothstep(0.78,0.52,fx);
      const L = 1 + v*0.13;
      d[o  ] = clamp(br*L + fox*16, 0,255);
      d[o+1] = clamp(bg*L + fox*4 , 0,255);
      d[o+2] = clamp(bb*L - fox*10, 0,255);
      d[o+3] = 255;
    }
  }
  x.putImageData(img,0,0);
  // soft plate vignette so the centre reads brighter under the "spotlight"
  const g=x.createRadialGradient(W*0.5,H*0.46,H*0.12,W*0.5,H*0.5,H*0.92);
  g.addColorStop(0,'rgba(255,250,240,0.10)');
  g.addColorStop(0.62,'rgba(0,0,0,0)');
  g.addColorStop(1,'rgba(60,40,24,0.17)');
  x.fillStyle=g; x.fillRect(0,0,W,H);
  return c;
}

// N grain frames, cycled at a reduced rate -> the hand-drawn "boil"
export function makeGrain(W,H,n=8,{amount=0.055,scale=1}={}){
  const out=[];
  for(let k=0;k<n;k++){
    const c=createCanvas(W,H),x=c.getContext('2d');
    const img=x.createImageData(W,H),d=img.data;
    const rnd=mulberry32(900+k*137);
    for(let p=0;p<W*H;p++){
      const o=p*4;
      const g=(rnd()-0.5);
      const v=128+g*255*amount*4;
      d[o]=d[o+1]=d[o+2]=clamp(v,0,255);
      d[o+3]=Math.min(255, Math.abs(g)*255*1.5);
    }
    x.putImageData(img,0,0);
    out.push(c);
  }
  return out;
}

// Torn deckle edge mask drawn over the frame
export function deckle(x,W,H,{inset=0,col=PAL.paper,amp=7,seed=3}={}){
  x.save(); x.fillStyle=col;
  const step=9;
  const edge=(fn)=>{x.beginPath();fn();x.closePath();x.fill();};
  // top
  edge(()=>{x.moveTo(0,0);x.lineTo(W,0);
    for(let i=W;i>=0;i-=step)x.lineTo(i, inset+ (fbm(i*0.013+seed,0.5,3)+0.5)*amp);
  });
  edge(()=>{x.moveTo(0,H);x.lineTo(W,H);
    for(let i=W;i>=0;i-=step)x.lineTo(i, H-inset-(fbm(i*0.013+seed+40,9.5,3)+0.5)*amp);
  });
  edge(()=>{x.moveTo(0,0);x.lineTo(0,H);
    for(let j=H;j>=0;j-=step)x.lineTo(inset+(fbm(0.5,j*0.013+seed+80,3)+0.5)*amp, j);
  });
  edge(()=>{x.moveTo(W,0);x.lineTo(W,H);
    for(let j=H;j>=0;j-=step)x.lineTo(W-inset-(fbm(9.5,j*0.013+seed+120,3)+0.5)*amp, j);
  });
  x.restore();
}
