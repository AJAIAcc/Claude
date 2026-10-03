import {createCanvas,registerFont} from 'canvas'; import fs from 'fs';
const F='assets/fonts/';
[['limelight-latin-400-normal','Limelight'],['josefin-sans-latin-700-normal','Josefin'],
 ['bodoni-moda-latin-400-italic','BodoniI'],['anton-latin-400-normal','Anton'],
 ['poiret-one-latin-400-normal','Poiret']].forEach(([f,fam])=>registerFont(F+f+'.ttf',{family:fam}));
const {makePaper,makeGrain,deckle}=await import('../src/core/paper.mjs');
const {PAL,rgba,mix}=await import('../src/core/palette.mjs');
const {rays,arcBands,halftone,inkText,chevrons,ziggurat,plates}=await import('../src/core/ink.mjs');
const W=1920,H=1080;
console.time('paper'); const paper=makePaper(W,H); console.timeEnd('paper');
console.time('grain'); const grains=makeGrain(W,H,4,{amount:0.05}); console.timeEnd('grain');
const c=createCanvas(W,H),x=c.getContext('2d');
console.time('frame');
x.drawImage(paper,0,0);
const cx=W/2, cy=H*0.47;
// gold ray fan behind
x.save();x.globalCompositeOperation='multiply';
rays(x,cx,cy,120,1150,28,{col:PAL.goldPale,a:0.5,rot:0.06,duty:0.5});
rays(x,cx,cy,120,900,28,{col:PAL.gold,a:0.22,rot:0.06+Math.PI/28,duty:0.34});
x.restore();
// halftone glow pool
halftone(x,cx-620,cy-360,1240,720,{col:PAL.terra,pitch:9,a:0.35,
  fn:(u,v)=>Math.max(0,1-Math.hypot((u-0.5)*2,(v-0.5)*2))});
// Deco arcs
x.save();x.globalCompositeOperation='multiply';
arcBands(x,cx,cy,[300,318,392],{col:PAL.ink,a:0.5,lw:4});
x.restore();
// ziggurat plinth
ziggurat(x,cx,H*0.90,760,210,5,{col:PAL.ink,a:0.14});
// TITLE with riso misregistration
const f1='400 170px "Limelight"';
plates(x,(xx,L)=>{inkText(xx,'TAKE A BOW',cx,cy-40,{font:f1,col:L.col,align:'center',base:'middle',bleed:0.2,spread:2.4,track:6});},
  [{col:PAL.pink,dx:-5,dy:3,a:0.55},{col:PAL.mint,dx:5,dy:-3,a:0.45},{col:PAL.ink,dx:0,dy:0,a:1}]);
inkText(x,'HUMANITY',cx,cy+105,{font:'400 118px "Limelight"',col:PAL.terra,align:'center',base:'middle',track:26,bleed:0.22,spread:2});
// rule + subtitle
x.save();x.globalCompositeOperation='multiply';x.strokeStyle=PAL.ink;x.globalAlpha=.65;x.lineWidth=3;
x.beginPath();x.moveTo(cx-330,cy+175);x.lineTo(cx+330,cy+175);x.stroke();x.restore();
inkText(x,'A  R E V U E  I N  O N E  A C T',cx,cy+222,{font:'400 30px "Josefin"',col:PAL.inkSoft,align:'center',base:'middle',track:7,bleed:0.1,spread:1});
// chevron border
chevrons(x,120,H-96,W-240,30,{col:PAL.ink,a:0.3,n:26,lw:5});
chevrons(x,120,66,W-240,30,{col:PAL.ink,a:0.3,n:26,lw:5,phase:1});
// grain + deckle
x.save();x.globalCompositeOperation='overlay';x.globalAlpha=0.5;x.drawImage(grains[0],0,0);x.restore();
deckle(x,W,H,{inset:0,amp:8});
console.timeEnd('frame');
fs.writeFileSync('analysis/t1.png',c.toBuffer('image/png'));
console.log('wrote analysis/t1.png');
