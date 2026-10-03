// THE HEADLINER — paper cut-out silhouette in the Lotte Reiniger tradition (1926),
// profile-facing, with a swept sunburst headdress from the Claude mark.
// Solid ink contour + pierced filigree. Faces +x; mirror with pose.face.
import {PAL,rgba,mix} from '../core/palette.mjs';
import {noise2,clamp} from '../core/noise.mjs';

export const POSE=()=>({
  x:0,y:0,s:1,face:1,
  lean:0, bob:0,
  headTilt:0, bloom:0.6, spin:0,
  armF:[-0.9,0.5], armB:[0.5,0.7],    // front / back arm  [shoulder, elbow]
  flare:0.5, sway:0, train:1,
  mouth:0, chin:0, veil:0,
});

const Hh=1000;

// ---- headdress: Claude's 11 rays as a Deco fan raking up and back ----
export function headdress(x,R,p,{col=PAL.ink,a=1,n=11}={}){
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  const b=p.bloom;
  // Claude's 11-ray burst as a Deco sun-fan rising BEHIND the skull, so the face
  // profile stays on the clean outer contour. theta: 0 = straight up, + = rake back.
  const T0=-0.16, T1=2.16, slot=(T1-T0)/(n-1);
  x.save(); x.rotate(p.spin*0.14); x.translate(-R*0.16,-R*0.04);
  for(let i=0;i<n;i++){
    const u=i/(n-1), th=T0+u*(T1-T0);
    const env=Math.sin(Math.PI*Math.pow(u,0.72));
    const Ri=R*0.72, Ro=Ri+R*(0.30+env*2.15)*(0.62+b*0.52);
    const hw=slot*0.42, tw=slot*0.14;
    // wedge, measured anticlockwise from +up, raked toward -x
    const A=(d)=>[-Math.sin(th+d)*0, 0];
    const pt=(r,d)=>[-Math.sin(th+d)*r, -Math.cos(th+d)*r];
    const p1=pt(Ri,-hw), p2=pt(Ri,hw), p3=pt(Ro,tw), p4=pt(Ro,-tw);
    x.beginPath();
    x.moveTo(p1[0],p1[1]); x.lineTo(p2[0],p2[1]);
    x.quadraticCurveTo((p2[0]+p3[0])/2*1.04,(p2[1]+p3[1])/2*1.04,p3[0],p3[1]);
    x.lineTo(p4[0],p4[1]);
    x.quadraticCurveTo((p4[0]+p1[0])/2*1.04,(p4[1]+p1[1])/2*1.04,p1[0],p1[1]);
    x.closePath(); x.fill();
  }
  x.restore(); x.restore();
}

// ---- profile head+body contour, one continuous cut ----
function bodyPath(x,p){
  const fl=p.flare, sw=p.sway, tr=p.train;
  // jaw articulation: the sung vocal drops the chin. In silhouette this is the
  // whole of lip-sync, and it is how cut-out animation has always done it.
  const m=Math.max(0,Math.min(1,p.mouth||0));
  const jd=m*34, jb=m*7;
  x.beginPath();
  x.moveTo(-34,-948);
  x.bezierCurveTo(-6,-972, 20,-964, 34,-938);          // skull top -> forehead
  x.bezierCurveTo(44,-922, 44,-910, 41,-899);          // brow
  x.bezierCurveTo(50,-890, 61,-879, 58,-872);          // nose
  x.bezierCurveTo(54,-868, 47,-867, 44,-865);          // under nose
  x.bezierCurveTo(53,-860, 54,-851, 47,-845);                        // upper lip (fixed)
  x.bezierCurveTo(50-jb*0.5,-840+jd*0.30, 49-jb,-831+jd*0.72, 42-jb,-825+jd);  // lower lip + chin
  x.bezierCurveTo(30-jb,-818+jd*0.82, 22-jb*0.6,-812+jd*0.45, 16,-806);        // jaw to throat
  x.bezierCurveTo(22,-792, 23,-776, 21,-762);          // throat
  x.bezierCurveTo(40,-756, 54,-744, 60,-726);          // shoulder -> bust
  x.bezierCurveTo(67,-700, 60,-668, 55,-634);
  x.bezierCurveTo(52,-600, 57,-578, 63,-560);          // dropped waist
  x.bezierCurveTo(68+fl*10+sw*14, -460, 74+fl*20+sw*40, -250, 84+fl*30+sw*72, -50);
  x.quadraticCurveTo(90+fl*36+sw*80, 6, 62+fl*26+sw*72, 9);              // narrow hem, front
  x.quadraticCurveTo(-16, 28, -104-tr*86+sw*54, 11);                      // hem sweeps back
  x.bezierCurveTo(-154-tr*140+sw*44, -22, -128-tr*100+sw*26, -170, -94-tr*54+sw*14, -352); // train
  x.bezierCurveTo(-80-tr*18, -452, -68, -516, -64, -562);
  x.bezierCurveTo(-58,-620, -56,-680, -50,-724);       // back
  x.bezierCurveTo(-46,-746, -34,-760, -20,-770);       // shoulder back
  x.bezierCurveTo(-16,-786, -16,-798, -18,-808);       // nape
  x.bezierCurveTo(-32,-842, -44,-880, -44,-908);       // back of skull
  x.bezierCurveTo(-44,-926, -40,-940, -34,-948);
  x.closePath();
}

// pierced filigree: negative-space cuts that make it read as cut paper
function pierce(x,p){
  x.save(); x.globalCompositeOperation='destination-out';
  // gown lattice — Deco diamonds down the skirt
  for(let r=0;r<6;r++){
    const y=-470+r*78, n=2+((r/2)|0)*2;
    for(let i=0;i<n;i++){
      const u=(i/(n-1||1)-0.5);
      const cx=u*(42+r*12)+p.sway*26, cy=y, s=6+r*1.5;
      x.beginPath();
      x.moveTo(cx,cy-s); x.lineTo(cx+s*0.62,cy); x.lineTo(cx,cy+s); x.lineTo(cx-s*0.62,cy);
      x.closePath(); x.fill();
    }
  }
  // bodice chevrons
  for(let k=0;k<3;k++){
    x.beginPath(); x.lineWidth=7; x.strokeStyle='#000';
    x.moveTo(-30,-700+k*34); x.lineTo(6,-714+k*34); x.lineTo(42,-700+k*34); x.stroke();
  }
  // eye slit
  x.beginPath(); x.ellipse(18,-898,11,5.5,-0.22,0,6.2832); x.fill();
  x.restore();
}

function arm(x,len,sh,el,w0,w1){
  x.save(); x.rotate(sh);
  x.beginPath();
  x.moveTo(-w0,0); x.lineTo(w0,0);
  x.quadraticCurveTo(w1*1.1,len*0.28, w1,len*0.52);
  x.lineTo(-w1,len*0.52);
  x.quadraticCurveTo(-w1*1.1,len*0.28,-w0,0);
  x.closePath(); x.fill();
  x.translate(0,len*0.50); x.rotate(el);
  x.beginPath();
  x.moveTo(-w1,0); x.lineTo(w1,0);
  x.quadraticCurveTo(w1*0.8,len*0.30, w1*0.46,len*0.48);
  x.lineTo(-w1*0.46,len*0.48);
  x.quadraticCurveTo(-w1*0.8,len*0.30,-w1,0);
  x.closePath(); x.fill();
  // long Deco hand
  x.save(); x.translate(0,len*0.48); x.rotate(-0.25);
  x.beginPath(); x.ellipse(0,len*0.055,w1*0.52,len*0.085,0,0,6.2832); x.fill();
  x.restore(); x.restore();
}

export function figure(x,p,S,{col=PAL.ink,a=1,pierced=true,rim=null}={}){
  x.save();
  x.translate(p.x,p.y);
  const sc=p.s*S;
  x.scale(sc*p.face,sc); x.globalAlpha=a;
  x.translate(0,p.bob); x.rotate(p.lean);

  // back arm first (behind body)
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  x.translate(-18,-752); arm(x,300,p.armB[0],p.armB[1],26,19); x.restore();

  // the cut-out itself, on its own layer so piercing can punch through
  x.save();
  x.fillStyle=col;
  x.save(); x.translate(0,0); x.rotate(0);
  bodyPath(x,p); x.fill();
  // headdress rotates with the head
  x.save(); x.translate(0,-886); x.rotate(p.headTilt);
  headdress(x,78,p,{col,a:1});
  x.restore();
  if(pierced) pierce(x,p);
  x.restore();
  x.restore();

  // front arm
  x.save(); x.globalAlpha=a; x.fillStyle=col;
  x.translate(34,-750); arm(x,300,p.armF[0],p.armF[1],27,20); x.restore();

  if(rim){ // thin lit edge along the front contour
    x.save(); x.globalAlpha=a*0.9; x.strokeStyle=rim; x.lineWidth=5; x.lineJoin='round';
    bodyPath(x,p); x.stroke(); x.restore();
  }
  x.restore();
}

// Chorus line: smaller cut-outs, alternating facing, legible en masse.
export function chorusFigure(x,cx,cy,s,ph,{col=PAL.ink,a=1,kick=0.9,face=1}={}){
  x.save(); x.translate(cx,cy); x.scale(s*face,s); x.globalAlpha=a; x.fillStyle=col;
  const k=Math.sin(ph)*kick;
  // headdress: few, WIDE wedges. Many thin rays read as fringe at this size.
  const n=6, T0=-0.10, T1=1.95, slot=(T1-T0)/(n-1);
  x.save(); x.translate(-3,-300);
  for(let i=0;i<n;i++){
    const u=i/(n-1), th=T0+u*(T1-T0);
    const env=Math.sin(Math.PI*Math.pow(u,0.75));
    const Ri=16, Ro=Ri+22+env*62, hw=slot*0.40, tw=slot*0.15;
    const pt=(r,d)=>[-Math.sin(th+d)*r,-Math.cos(th+d)*r];
    const p1=pt(Ri,-hw),p2=pt(Ri,hw),p3=pt(Ro,tw),p4=pt(Ro,-tw);
    x.beginPath(); x.moveTo(p1[0],p1[1]); x.lineTo(p2[0],p2[1]);
    x.lineTo(p3[0],p3[1]); x.lineTo(p4[0],p4[1]); x.closePath(); x.fill();
  }
  x.restore();
  // head in profile + neck
  x.beginPath(); x.ellipse(2,-300,19,23,0,0,6.2832); x.fill();
  x.beginPath(); x.moveTo(12,-302); x.lineTo(24,-296); x.lineTo(14,-288); x.closePath(); x.fill();
  x.fillRect(-4,-282,12,28);
  // arms: raised, with a real elbow bend, ending in a hand — not a stick
  for(const sd of [1,-1]){
    x.save(); x.translate(sd*14,-252); x.rotate(sd*(2.08+Math.sin(ph+sd*0.9)*0.22));
    x.beginPath(); x.moveTo(-7,0); x.lineTo(7,0); x.lineTo(4,78); x.lineTo(-5,78); x.closePath(); x.fill();
    x.translate(0,76); x.rotate(sd*-0.50);
    x.beginPath(); x.moveTo(-5,0); x.lineTo(5,0); x.lineTo(3,66); x.lineTo(-4,66); x.closePath(); x.fill();
    x.beginPath(); x.ellipse(0,68,6,10,0,0,6.2832); x.fill();
    x.restore();
  }
  // 1920s column with a kicked hem
  x.beginPath();
  x.moveTo(-16,-254); x.quadraticCurveTo(8,-266,18,-246);
  x.quadraticCurveTo(23,-168,20,-92);
  x.quadraticCurveTo(34,-42,46,6);
  x.quadraticCurveTo(-14,24,-54,4);
  x.quadraticCurveTo(-36,-44,-20,-92);
  x.quadraticCurveTo(-23,-170,-16,-254);
  x.closePath(); x.fill();
  // the kicking leg breaks the hem line
  x.save(); x.translate(6,-104); x.rotate(k*0.52);
  x.beginPath(); x.moveTo(-8,0); x.lineTo(8,0); x.lineTo(4,108); x.lineTo(-7,108); x.closePath(); x.fill();
  x.beginPath(); x.ellipse(-1,110,8,5,0,0,6.2832); x.fill();
  x.restore();
  x.restore();
}
