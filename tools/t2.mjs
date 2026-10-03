import {createCanvas,registerFont} from 'canvas'; import fs from 'fs';
const F='assets/fonts/';
[['limelight-latin-400-normal','Limelight'],['josefin-sans-latin-700-normal','Josefin'],
 ['josefin-sans-latin-400-normal','JosefinR']].forEach(([f,fam])=>registerFont(F+f+'.ttf',{family:fam}));
const {makePaper,makeGrain}=await import('../src/core/paper.mjs');
const {PAL,rgba}=await import('../src/core/palette.mjs');
const {inkText,rays}=await import('../src/core/ink.mjs');
const {figure,POSE,chorusFigure}=await import('../src/character/headliner.mjs');
const W=1800,H=1340,c=createCanvas(W,H),x=c.getContext('2d');
x.drawImage(makePaper(W,H),0,0);
// warm pools behind so silhouettes read
for(let i=0;i<3;i++){const g=x.createRadialGradient(300+i*600,470,20,300+i*600,470,330);
 g.addColorStop(0,rgba(PAL.goldPale,0.55));g.addColorStop(1,rgba(PAL.goldPale,0));x.fillStyle=g;x.fillRect(0,100,W,780);}
inkText(x,'THE HEADLINER',W/2,62,{font:'400 54px "Limelight"',col:PAL.ink,align:'center',base:'middle',track:8});
inkText(x,'paper cut-out silhouette  ·  after Lotte Reiniger, 1926',W/2,106,
  {font:'400 22px "JosefinR"',col:PAL.inkSoft,align:'center',base:'middle',track:2,bleed:0});
const poses=[
  ['at rest',    p=>{p.armF=[-0.5,0.55];p.armB=[0.4,0.6];}],
  ['presenting', p=>{p.armF=[-2.1,0.5];p.armB=[0.6,0.5];p.bloom=0.85;p.mouth=.6;p.lean=-0.04;}],
  ['arms wide',  p=>{p.armF=[-2.0,-0.5];p.armB=[1.9,0.45];p.bloom=1;p.lean=-0.07;p.flare=0.75;}],
  ['sly aside',  p=>{p.armF=[-1.0,1.5];p.armB=[0.3,0.5];p.headTilt=0.16;p.bloom=0.35;p.lean=0.05;}],
  ['the bow',    p=>{p.lean=0.62;p.armF=[-1.9,0.8];p.armB=[1.0,0.7];p.bloom=0.5;p.train=1.5;}],
  ['mirrored',   p=>{p.face=-1;p.armF=[-1.75,0.45];p.armB=[0.7,0.6];p.bloom=0.9;p.flare=0.7;}],
];
poses.forEach(([name,fn],i)=>{
  const col=i%3,row=(i/3)|0, cx=300+col*600, cy=560+row*430;
  const p=POSE(); p.x=cx; p.y=cy; fn(p);
  figure(x,p,0.40);
  inkText(x,name,cx,cy+44,{font:'400 24px "Josefin"',col:PAL.inkSoft,align:'center',base:'middle',track:3,bleed:0});
});
for(let i=0;i<8;i++) chorusFigure(x,180+i*210,1300,0.33,i*0.8,{a:0.9,face:i%2?1:-1});
x.save();x.globalCompositeOperation='overlay';x.globalAlpha=.42;x.drawImage(makeGrain(W,H,1)[0],0,0);x.restore();
fs.writeFileSync('analysis/charsheet.png',c.toBuffer('image/png'));
console.log('ok');
