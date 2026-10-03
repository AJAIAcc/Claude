// "THE LAST REVUE" palette: 1920s period-correct + Claude terracotta + one modern accent.
export const PAL={
  paper:'#F3EADA', paperDeep:'#E8DAC2', paperShade:'#D9C7A9',
  ink:'#241C19', inkSoft:'#3A2E28',
  terra:'#D4714E',  terraDeep:'#B4543A',
  gold:'#C9A227',   goldPale:'#E3C96A',
  pink:'#E0577F',
  mint:'#7FC4B0',
  ox:'#6E1F2A',
  night:'#14100E',
};
export const hex2rgb=h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];
export const rgba=(h,a)=>{const[r,g,b]=hex2rgb(h);return`rgba(${r},${g},${b},${a})`;};
export function mix(h1,h2,t){const a=hex2rgb(h1),b=hex2rgb(h2);
  return`rgb(${Math.round(a[0]+(b[0]-a[0])*t)},${Math.round(a[1]+(b[1]-a[1])*t)},${Math.round(a[2]+(b[2]-a[2])*t)})`;}
