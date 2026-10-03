import fs from 'fs';
const {createRenderer}=await import('../src/render.mjs');
const W=+(process.env.W||1280), H=+(process.env.H||720);
const R=createRenderer(W,H,{root:'.',grainN:2});
const ts=process.argv.slice(2).map(Number);
fs.mkdirSync('out/stills',{recursive:true});
for(const t of ts){
  const c=R.drawFrame(t);
  const n=`out/stills/t${t.toFixed(2).replace('.','_')}.png`;
  fs.writeFileSync(n,c.toBuffer('image/png'));
  console.log(n);
}
