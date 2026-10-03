// Lyric typography: slam-in hero type, subtitles, call/response, velvet, choir.
import {PAL,rgba,mix} from './palette.mjs';
import {inkText,measure,spaceW,rays,halftone,chevrons} from './ink.mjs';
import {clamp,smoothstep,noise2} from './noise.mjs';

const ease={
  outBack:(t,s=1.70158)=>{const u=t-1;return 1+(s+1)*u*u*u+s*u*u;},
  outExpo:t=>t>=1?1:1-Math.pow(2,-10*t),
  outQuint:t=>1-Math.pow(1-t,5),
  inQuad:t=>t*t,
  outCubic:t=>1-Math.pow(1-t,3),
};
export {ease};

function words(txt){return txt.split(/(\s+)/).filter(w=>w.trim().length);}

// Lay words into lines that fit maxW at the given font.
export function wrap(x,txt,font,maxW,track=0){
  x.save(); x.font=font;
  const fsm=parseFloat((font.match(/(\d+(?:\.\d+)?)px/)||[0,16])[1]);
  const sp=spaceW(x,font,fsm,track);
  const ws=words(txt), out=[]; let cur=[], curW=0;
  for(const w of ws){
    const ww=measure(x,w,font,track);
    const test=curW+(cur.length?sp:0)+ww;
    if(test>maxW&&cur.length){out.push(cur.join(' '));cur=[w];curW=ww;}
    else {cur.push(w);curW=test;}
  }
  if(cur.length)out.push(cur.join(' '));
  x.restore(); return out;
}

// ---- HERO: huge Deco type, per-word slam with riso fringing ----
export function hero(x,W,H,txt,p,{cy=H*0.5,size=null,col=PAL.ink,accent=PAL.terra,
  maxW=W*0.84,emph=null,beat=0,track=null}={}){
  const fs=size|| clamp(W*0.082*(14/Math.max(10,txt.length))*2.0, W*0.040, W*0.105);
  const tr = track==null ? fs*0.085 : track;
  const font=`400 ${fs}px "Limelight"`;
  const lines=wrap(x,txt,font,maxW,tr);
  const lh=fs*1.16;
  const y0=cy-(lines.length-1)*lh/2;
  lines.forEach((ln,li)=>{
    const ws=words(ln);
    const widths=ws.map(w=>measure(x,w,font,tr));
    const spc=spaceW(x,font,fs,tr);
    const total=widths.reduce((a,b)=>a+b,0)+spc*(ws.length-1);
    let sx=W/2-total/2;
    ws.forEach((w,wi)=>{
      const d=(li*ws.length+wi)*0.055;
      const t=clamp((p-d)/0.30,0,1);
      if(t<=0){sx+=widths[wi]+spc;return;}
      const e=ease.outBack(t,2.2);
      const sc=0.72+0.28*e, dy=(1-e)*fs*0.30, al=clamp(t*2.2,0,1);
      const isE = emph && w.replace(/[^\w']/g,'').toLowerCase()===emph.toLowerCase();
      const c = isE? accent : col;
      x.save();
      x.translate(sx+widths[wi]/2, y0+li*lh+dy);
      x.scale(sc,sc);
      const mis=(1-t)*7;
      x.globalCompositeOperation='multiply';
      inkText(x,w,-widths[wi]/2-mis,0,{font,col:PAL.pink,align:'left',base:'middle',a:al*0.55,track:tr,bleed:0.12,spread:2});
      inkText(x,w, -widths[wi]/2+mis,0,{font,col:PAL.mint,align:'left',base:'middle',a:al*0.45,track:tr,bleed:0.12,spread:2});
      x.globalCompositeOperation='source-over';
      inkText(x,w,-widths[wi]/2,0,{font,col:c,align:'left',base:'middle',a:al,track:tr,bleed:0.22,spread:fs*0.018});
      x.restore();
      sx+=widths[wi]+spc;
    });
  });
  return {fs,lines:lines.length,lh};
}

// ---- SUBTITLE: lower third, geometric sans, understated ----
export function subtitle(x,W,H,txt,p,{cy=H*0.845,col=PAL.ink,accent=PAL.terra,
  size=null,emph=null,maxW=W*0.72,align='center',rule=true}={}){
  const fs=size||W*0.0248;
  const font=`600 ${fs}px "Josefin"`;
  const lines=wrap(x,txt,font,maxW,1.2);
  const lh=fs*1.30, a=clamp(p/0.18,0,1)*clamp((1-p)/0.10+1,0,1);
  const sl=(1-ease.outQuint(clamp(p/0.26,0,1)))*fs*0.55;
  lines.forEach((ln,li)=>{
    const y=cy+li*lh+sl;
    if(emph){
      const ws=words(ln); const widths=ws.map(w=>measure(x,w,font,1.2));
      const spc=spaceW(x,font,fs,1.2);
      const total=widths.reduce((s,b)=>s+b,0)+spc*(ws.length-1);
      let sx=align==='center'?W/2-total/2:W*0.09;
      ws.forEach((w,wi)=>{
        const isE=w.replace(/[^\w']/g,'').toLowerCase()===emph.toLowerCase();
        inkText(x,w,sx,y,{font:isE?`700 ${fs*1.16}px "Josefin"`:font,
          col:isE?accent:col,align:'left',base:'middle',a,track:1.2,bleed:0.12,spread:1.4});
        sx+=widths[wi]+spc;
      });
    } else {
      inkText(x,ln,align==='center'?W/2:W*0.09,y,{font,col,align,base:'middle',a,track:1.2,bleed:0.12,spread:1.4});
    }
  });
  if(rule&&a>0.2){
    x.save(); x.globalAlpha=a*0.45; x.strokeStyle=col; x.lineWidth=2.5;
    const w=W*0.09*ease.outQuint(clamp(p/0.4,0,1));
    x.beginPath(); x.moveTo(W/2-w,cy-fs*0.95); x.lineTo(W/2+w,cy-fs*0.95); x.stroke(); x.restore();
  }
  return {fs,lh,lines:lines.length};
}

// ---- SLAM: brutal modern condensed, the machine voice ----
export function slam(x,W,H,txt,p,{cy=H*0.5,col=PAL.ink,bg=null,maxW=W*0.9}={}){
  const fs=clamp(W*1.10/Math.max(5,txt.length), W*0.07, W*0.20);
  const font=`400 ${fs}px "Anton"`;
  const t=clamp(p/0.12,0,1), e=ease.outExpo(t);
  const sc=1.45-0.45*e, a=clamp(t*3,0,1);
  x.save(); x.translate(W/2,cy); x.scale(sc,sc*(0.92+0.08*e)); x.globalAlpha=a;
  if(bg){ const w=measure(x,txt,font,2)*1.10, h=fs*1.12;
    x.fillStyle=bg; x.fillRect(-w/2,-h/2,w,h); }
  const mis=(1-e)*14;
  x.globalCompositeOperation='multiply';
  inkText(x,txt,-mis,0,{font,col:PAL.pink,align:'center',base:'middle',a:0.6,track:2,bleed:0.1,spread:2});
  inkText(x,txt, mis,0,{font,col:PAL.mint,align:'center',base:'middle',a:0.5,track:2,bleed:0.1,spread:2});
  x.globalCompositeOperation='source-over';
  inkText(x,txt,0,0,{font,col,align:'center',base:'middle',a:1,track:2,bleed:0.2,spread:fs*0.02});
  x.restore();
}

// ---- VELVET: the bridge. Bodoni italic, slow, intimate ----
export function velvet(x,W,H,txt,p,{cy=H*0.52,cx=null,align='center',col=PAL.paper,maxW=W*0.62,size=null}={}){
  const fs=size||W*0.0355, font=`400 ${fs}px "BodoniI"`;
  const X=cx==null?W/2:cx;
  const lines=wrap(x,txt,font,maxW,0.5), lh=fs*1.42;
  const y0=cy-(lines.length-1)*lh/2;
  lines.forEach((ln,li)=>{
    const t=clamp((p-li*0.10)/0.62,0,1), e=ease.outCubic(t);
    inkText(x,ln,X,y0+li*lh+(1-e)*10,{font,col,align,base:'middle',
      a:e*clamp((1-p)*5,0,1),track:0.5,bleed:0.1,spread:1.6});
  });
}

// ---- CALL & RESPONSE: the pre-chorus ----
export function callResp(x,W,H,txt,p,isResp,{col=PAL.ink,accent=PAL.pink}={}){
  const fs=isResp? W*0.046 : W*0.068;
  const font=`400 ${fs}px "Limelight"`;
  const t=clamp(p/0.10,0,1), e=ease.outBack(t,3.0);
  const cx=isResp? W*0.68 : W*0.40;
  const cy=isResp? H*0.60 : H*0.42;
  x.save(); x.translate(cx,cy+ (1-e)*(isResp?40:-60)); x.scale(0.6+0.4*e,0.6+0.4*e);
  x.globalAlpha=clamp(t*3,0,1)*clamp((1-p)*4,0,1);
  if(!isResp) rays(x,0,0,fs*0.7,fs*2.6,16,{col:PAL.gold,a:0.22*e,rot:p*0.5});
  inkText(x,txt,0,0,{font,col:isResp?accent:col,align:'center',base:'middle',track:6,bleed:0.2,spread:fs*0.02});
  x.restore();
}

// ---- CHOIR: stacked gang vocals ----
export function choirLine(x,W,H,txt,p,idx,{col=PAL.paper,accent=PAL.goldPale}={}){
  const fs=W*0.030, font=`600 ${fs}px "Josefin"`;
  const t=clamp(p/0.14,0,1), e=ease.outQuint(t);
  const y=H*0.30+idx*fs*1.5;
  x.save(); x.globalAlpha=clamp(t*3,0,1)*clamp((1-p)*3,0,1)*0.95;
  inkText(x,txt,W/2+(1-e)*((idx%2)?60:-60),y,{font,col:(idx%2)?accent:col,
    align:'center',base:'middle',track:2,bleed:0.12,spread:1.5});
  x.restore();
}
