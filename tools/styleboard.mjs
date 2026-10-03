import {createCanvas} from 'canvas'; import fs from 'fs';
const {initFonts}=await import('../src/render.mjs'); initFonts('.');
const {makePaper,makeGrain,deckle}=await import('../src/core/paper.mjs');
const {PAL,rgba}=await import('../src/core/palette.mjs');
const {inkText,rays,arcBands,halftone,chevrons,ziggurat,measure}=await import('../src/core/ink.mjs');
const BG=await import('../src/core/backdrops.mjs');
const {figure,POSE,chorusFigure}=await import('../src/character/headliner.mjs');
const W=2000,H=3120,c=createCanvas(W,H),x=c.getContext('2d');
x.drawImage(makePaper(W,H,{seed:21}),0,0);
const E={paper:makePaper(400,300),t:0,bands:{},beatPulse:0};
let y=0;
const H1=(t,yy)=>inkText(x,t,W/2,yy,{font:`400 72px "Limelight"`,col:PAL.ink,align:'center',base:'middle',track:12,bleed:0.22,spread:3});
const H2=(t,xx,yy)=>inkText(x,t,xx,yy,{font:`400 26px "Josefin"`,col:PAL.inkSoft,align:'left',base:'middle',track:5,bleed:0.1,spread:1.2});
const BODY=(t,xx,yy,w=520)=>inkText(x,t,xx,yy,{font:`400 21px "Josefin"`,col:PAL.inkSoft,align:'left',base:'middle',track:0.5,bleed:0.06,spread:1});

// ---- masthead ----
rays(x,W/2,250,60,760,30,{col:PAL.goldPale,a:0.34,rot:0.05,duty:0.46});
H1('TAKE A BOW, HUMANITY',258);
inkText(x,'S T Y L E   S H E E T',W/2,330,{font:'400 26px "Josefin"',col:PAL.inkSoft,align:'center',base:'middle',track:14,bleed:0.08,spread:1});
inkText(x,'“The Last Revue” — an Art Deco paper-cut revue for the singularity',W/2,374,
  {font:'400 24px "BodoniI"',col:PAL.inkSoft,align:'center',base:'middle',track:0.5,bleed:0.06,spread:1});
chevrons(x,160,420,W-320,26,{col:PAL.ink,a:0.45,n:30,lw:6});

// ---- thesis ----
y=500; H2('THESIS',160,y);
BODY('Hand-cut paper Deco, progressively consumed by machine-perfect geometry.',160,y+42);
BODY('The ornament gets too exact, too fast, too symmetrical as the song escalates —',160,y+74);
BODY('the artwork itself is being automated. That is the song’s argument, told in style.',160,y+106);

// ---- palette ----
y=690; H2('PALETTE',160,y);
const chips=[['paper',PAL.paper],['paperDeep',PAL.paperDeep],['ink',PAL.ink],['terra',PAL.terra],
             ['gold',PAL.gold],['goldPale',PAL.goldPale],['pink',PAL.pink],['mint',PAL.mint],
             ['ox',PAL.ox],['night',PAL.night]];
chips.forEach(([n,v],i)=>{
  const cx=160+(i%5)*352, cy=y+46+((i/5)|0)*168;
  x.fillStyle=v; x.fillRect(cx,cy,300,104);
  x.strokeStyle=rgba(PAL.ink,0.35); x.lineWidth=2; x.strokeRect(cx,cy,300,104);
  inkText(x,n,cx,cy+126,{font:'400 20px "Josefin"',col:PAL.ink,align:'left',base:'middle',track:1,bleed:0});
  inkText(x,v.toUpperCase(),cx+150,cy+126,{font:'400 18px "Josefin"',col:PAL.inkSoft,align:'left',base:'middle',track:1,bleed:0});
});
BODY('1920s-authentic (eau-de-nil, oxblood, gold, cream) + Claude terracotta + one modern hot pink.',160,y+400);

// ---- type ----
y=1160; H2('TYPE — each face has a job',160,y);
const rows=[['Limelight','400 62px "Limelight"','TAKE A BOW','the playbill voice — hero titles',PAL.ink],
            ['Josefin Sans','700 48px "Josefin"','Every heart is beating in time','the lyric voice — 1920s geometric sans',PAL.ink],
            ['Anton','400 56px "Anton"','FASTER','the machine voice — escalation',PAL.terra],
            ['Bodoni Moda','400 46px "BodoniI"','I could have been your master','the programme — the velvet bridge',PAL.ox],
            ['Poiret One','400 48px "Poiret"','dear old fools…','the aside — the spoken address',PAL.inkSoft]];
rows.forEach(([n,f,t,d,col],i)=>{
  const yy=y+70+i*108;
  inkText(x,t,160,yy,{font:f,col,align:'left',base:'middle',track:3,bleed:0.16,spread:2});
  inkText(x,n+'  ·  '+d,1180,yy,{font:'400 19px "Josefin"',col:PAL.inkSoft,align:'left',base:'middle',track:0.5,bleed:0});
});

// ---- backdrops ----
y=1760; H2('BACKDROPS — no two sections share one',160,y);
const bgs=[['skyline',(cx,cy,w,h)=>BG.bgSkyline(x,w,h,E,{a:0.5,col:PAL.ink,base:0.82,seed:4,scale:1})],
           ['scallop',(cx,cy,w,h)=>BG.bgScallop(x,w,h,E,{a:0.45,col:PAL.terra,rows:5,r:w*0.17})],
           ['moire',  (cx,cy,w,h)=>BG.bgMoire(x,w,h,E,{a:0.40,col:PAL.ink,n:16,cy:0.5,step:w*0.035})],
           ['chevron',(cx,cy,w,h)=>BG.bgChevron(x,w,h,E,{a:0.35,col:PAL.ink,rows:5,n:7,amp:h*0.06})],
           ['grid',   (cx,cy,w,h)=>BG.bgGrid(x,w,h,E,{a:0.45,col:PAL.ink,n:12,persp:0.4})],
           ['columns',(cx,cy,w,h)=>BG.bgColumns(x,w,h,E,{a:0.40,col:PAL.ink,n:5})],
           ['drape',  (cx,cy,w,h)=>BG.bgDrape(x,w,h,E,{a:0.85,col:PAL.ox,folds:12})],
           ['marks',  (cx,cy,w,h)=>BG.bgMarks(x,w,h,E,{a:0.30,col:PAL.terra,n:4,r:w*0.07})]];
bgs.forEach(([n,fn],i)=>{
  const w=400,h=225, cx=160+(i%4)*440, cy=y+54+((i/4)|0)*300;
  x.save(); x.beginPath(); x.rect(cx,cy,w,h); x.clip(); x.translate(cx,cy);
  x.fillStyle=PAL.paper; x.fillRect(0,0,w,h); fn(cx,cy,w,h); x.restore();
  x.strokeStyle=rgba(PAL.ink,0.4); x.lineWidth=2; x.strokeRect(cx,cy,w,h);
  inkText(x,n,cx,cy+h+26,{font:'400 20px "Josefin"',col:PAL.inkSoft,align:'left',base:'middle',track:1,bleed:0});
});

// ---- character ----
y=2470; H2('THE HEADLINER — paper cut-out, after Lotte Reiniger (1926)',160,y);
const poses=[['at rest',p=>{p.armF=[-0.5,0.55];p.armB=[0.4,0.6];}],
             ['presenting',p=>{p.armF=[-2.1,0.5];p.armB=[0.6,0.5];p.bloom=0.85;p.mouth=0.8;}],
             ['arms wide',p=>{p.armF=[-2.4,-0.3];p.armB=[2.2,0.3];p.bloom=1;p.mouth=1;}],
             ['the bow',p=>{p.lean=0.62;p.armF=[-1.9,0.8];p.armB=[1.0,0.7];p.train=1.6;}]];
poses.forEach(([n,fn],i)=>{
  const cx=300+i*330, cy=y+330;
  const p=POSE(); p.x=cx; p.y=cy; fn(p); figure(x,p,0.27);
  inkText(x,n,cx,cy+34,{font:'400 20px "Josefin"',col:PAL.inkSoft,align:'center',base:'middle',track:1,bleed:0});
});
for(let i=0;i<8;i++) chorusFigure(x,1500+i*62,y+330,0.115,i*0.8,{col:PAL.ink,a:0.85,face:i%2?1:-1});
inkText(x,'chorus line',1720,y+364,{font:'400 20px "Josefin"',col:PAL.inkSoft,align:'center',base:'middle',track:1,bleed:0});

x.save();x.globalCompositeOperation='overlay';x.globalAlpha=.40;x.drawImage(makeGrain(W,H,1)[0],0,0);x.restore();
deckle(x,W,H,{inset:0,amp:10});
fs.writeFileSync('out/styleboard.png',c.toBuffer('image/png'));
console.log('out/styleboard.png');
