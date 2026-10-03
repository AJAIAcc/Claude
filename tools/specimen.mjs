import {createCanvas, registerFont} from 'canvas'; import fs from 'fs';
const F='assets/fonts/';
const reg=[['limelight-latin-400-normal','Limelight',400],['poiret-one-latin-400-normal','Poiret',400],
['josefin-sans-latin-700-normal','Josefin',700],['josefin-sans-latin-400-normal','Josefin',400],
['playfair-display-latin-900-normal','Playfair',900],['bodoni-moda-latin-700-normal','Bodoni',700],
['bodoni-moda-latin-400-italic','BodoniI',400],['cinzel-decorative-latin-900-normal','Cinzel',900],
['anton-latin-400-normal','Anton',400],['archivo-black-latin-400-normal','Archivo',400]];
for(const [f,fam,w] of reg) registerFont(F+f+'.ttf',{family:fam,weight:String(w)});
const W=1500,H=1500,c=createCanvas(W,H),x=c.getContext('2d');
x.fillStyle='#F3EADA';x.fillRect(0,0,W,H);
const PAL={ink:'#241C19',terra:'#D4714E',gold:'#C9A227',pink:'#E0577F',mint:'#7FC4B0',ox:'#6E1F2A'};
let y=70;
const rows=[['Limelight',700,'TAKE A BOW',PAL.ink],['Cinzel',900,'TAKE A BOW',PAL.ox],
['Playfair',900,'TAKE A BOW',PAL.ink],['Bodoni',700,'TAKE A BOW',PAL.ink],
['Anton',400,'TAKE A BOW',PAL.terra],['Archivo',400,'TAKE A BOW',PAL.pink],
['Josefin',700,'TAKE A BOW, HUMANITY',PAL.ink],['Poiret',400,'take a bow, humanity',PAL.ink]];
for(const [fam,w,txt,col] of rows){
  x.font=`${w} 74px "${fam}"`; x.fillStyle=col; x.fillText(txt,60,y+62);
  x.font='400 17px "Josefin"'; x.fillStyle='#8a7d70'; x.fillText(fam,60,y+92);
  y+=132;
}
// lyric-scale comparison
y+=10; x.fillStyle=PAL.ink;
x.font='600 40px "Josefin"'; x.fillText("Every heart is beating in time,",60,y+=50);
x.font='400 40px "Poiret"';   x.fillText("Every heart is beating in time,",60,y+=58);
x.font='400 38px "BodoniI"';  x.fillText("Every heart is beating in time,",60,y+=58);
x.font='400 40px "Anton"';    x.fillText("THE FUTURE'S HERE",60,y+=60);
// palette chips
y+=40; let px=60;
for(const [k,v] of Object.entries(PAL)){
  x.fillStyle=v;x.fillRect(px,y,150,86);
  x.fillStyle='#241C19';x.font='400 15px "Josefin"';x.fillText(k+' '+v,px,y+106); px+=168;
}
fs.writeFileSync('analysis/specimen.png',c.toBuffer('image/png'));
console.log('wrote analysis/specimen.png');
