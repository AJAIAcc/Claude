import w from 'wawoff2'; import fs from 'fs'; 
const want=[['limelight','limelight-latin-400-normal'],['poiret-one','poiret-one-latin-400-normal'],
['josefin-sans','josefin-sans-latin-700-normal'],['josefin-sans','josefin-sans-latin-600-normal'],
['josefin-sans','josefin-sans-latin-400-normal'],
['playfair-display','playfair-display-latin-900-normal'],['playfair-display','playfair-display-latin-700-italic'],
['bodoni-moda','bodoni-moda-latin-700-normal'],['bodoni-moda','bodoni-moda-latin-400-normal'],
['bodoni-moda','bodoni-moda-latin-400-italic'],
['cinzel-decorative','cinzel-decorative-latin-700-normal'],['cinzel-decorative','cinzel-decorative-latin-900-normal'],
['anton','anton-latin-400-normal'],['archivo-black','archivo-black-latin-400-normal']];
fs.mkdirSync('assets/fonts',{recursive:true});
for(const [p,f] of want){
  const src=`node_modules/@fontsource/${p}/files/${f}.woff2`;
  if(!fs.existsSync(src)){console.log('MISS',f);continue;}
  fs.writeFileSync(`assets/fonts/${f}.ttf`,Buffer.from(await w.decompress(fs.readFileSync(src))));
}
console.log('fonts ->',fs.readdirSync('assets/fonts').length);
