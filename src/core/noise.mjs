// Deterministic value / simplex-ish noise + helpers. No deps.
export function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const P=new Uint8Array(512);{const r=mulberry32(1337);const p=[...Array(256).keys()];
for(let i=255;i>0;i--){const j=(r()*(i+1))|0;[p[i],p[j]]=[p[j],p[i]];}for(let i=0;i<512;i++)P[i]=p[i&255];}
const fade=t=>t*t*t*(t*(t*6-15)+10);
const lerp=(a,b,t)=>a+(b-a)*t;
function grad(h,x,y){switch(h&3){case 0:return x+y;case 1:return-x+y;case 2:return x-y;default:return-x-y;}}
export function noise2(x,y){
  const X=Math.floor(x)&255,Y=Math.floor(y)&255;x-=Math.floor(x);y-=Math.floor(y);
  const u=fade(x),v=fade(y);
  const aa=P[P[X]+Y],ab=P[P[X]+Y+1],ba=P[P[X+1]+Y],bb=P[P[X+1]+Y+1];
  return lerp(lerp(grad(aa,x,y),grad(ba,x-1,y),u),lerp(grad(ab,x,y-1),grad(bb,x-1,y-1),u),v);
}
export function fbm(x,y,oct=4,lac=2.0,gain=0.5){
  let a=0.5,f=1,s=0,n=0;
  for(let i=0;i<oct;i++){s+=a*noise2(x*f,y*f);n+=a;a*=gain;f*=lac;}
  return s/n;
}
export const clamp=(v,a,b)=>v<a?a:v>b?b:v;
export const smoothstep=(e0,e1,x)=>{const t=clamp((x-e0)/(e1-e0),0,1);return t*t*(3-2*t);};
