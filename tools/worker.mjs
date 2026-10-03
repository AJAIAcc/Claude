import fs from 'fs';
const [,,a,b,W,H,outDir,grainN]=process.argv;
const {createRenderer}=await import('../src/render.mjs');
const R=createRenderer(+W,+H,{root:'.',grainN:+grainN});
const FPS=30;
for(let f=+a; f<+b; f++){
  const c=R.drawFrame(f/FPS);
  fs.writeFileSync(`${outDir}/${String(f).padStart(6,'0')}.jpg`, c.toBuffer('image/jpeg',{quality:0.95}));
  if((f-+a)%200===0) process.stdout.write(`w${a} ${f-+a}/${+b-+a}\n`);
}
process.stdout.write(`w${a} done\n`);
