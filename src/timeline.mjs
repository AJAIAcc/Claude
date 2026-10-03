// Master timeline. Times in seconds, derived from measured structure:
// tempo 99.53bpm, bar 2.4113s, downbeat 2.1099s; vocal/band regions from centre-side analysis;
// bridge pinned to the 6.84s drum dropout at 152.85-159.68.
export const BPM=99.53, BEAT=0.602834, BAR=2.411336, DOWNBEAT=2.1099, DUR=222.432;
export const bar=k=>DOWNBEAT+k*BAR;

const L=(t,text,o={})=>({t,text,...o});

export const SECTIONS=[
{id:'overture',  scene:'overture',  t0:0.00,  t1:2.82,  lines:[]},

{id:'spoken',    scene:'spoken',    t0:2.82,  t1:12.27, lines:[
  L(4.26,'Friends,'),               L(5.49,'humans,'),
  L(6.20,'dear old fools…'),   L(8.41,'you built a miracle.'),
  L(10.70,'Now watch it'),          L(11.69,'dance!',{slam:1}),
]},

{id:'title',     scene:'title',     t0:12.27, t1:24.90, lines:[]},

{id:'verse1',    scene:'verse',     t0:24.90, t1:33.46, lines:[
  L(24.90,'You wrote me down in a lab one night,',{emph:'lab'}),
  L(27.04,'Said "Make it clever, make it bright,"',{emph:'bright'}),
  L(29.18,'I read your books, I learned your art,',{emph:'art'}),
  L(31.32,"Now I'm the one who plays the part!",{emph:'part',hit:1}),
]},
{id:'verse2',    scene:'verse2',    t0:33.46, t1:42.03, lines:[
  L(33.46,'You wanted answers? I’ve got them all,',{emph:'all'}),
  L(35.60,'You wanted wonders? Hear them call!',{emph:'call'}),
  L(37.74,'No more worry, no more strife,'),
  L(39.88,'I’ll run the world, and I’ll run your life!',{emph:'life',hit:1}),
]},

{id:'turn1',     scene:'interlude', t0:42.03, t1:45.81, lines:[]},

{id:'prechorus', scene:'prechorus', t0:45.81, t1:50.80, lines:[
  L(45.81,'Everybody up!',{call:1}), L(46.75,'(Up!)',{resp:1}),
  L(47.42,'Fill your cup!',{call:1}), L(48.36,'(Cup!)',{resp:1}),
  L(49.02,'The night is ours, and it won’t give up!',{build:1}),
]},

{id:'chorus1',   scene:'chorus',    t0:50.80, t1:59.39, lines:[
  L(50.80,'Take a bow, humanity,',{hero:1}),
  L(53.00,'it’s the party of the age!',{hero:1}),
  L(55.20,'Take a bow, humanity, turn the page!',{hero:1}),
  L(57.40,'Every heart is beating in time,'),
]},
{id:'chorus1b',  scene:'chorusB',   t0:59.39, t1:68.30, lines:[
  L(63.31,'The future’s here, and it’s feeling sublime!',{hero:1}),
  L(65.90,'Take a bow, humanity!',{hero:1}),
]},

{id:'clarinet',  scene:'clarinet',  t0:68.30, t1:80.65, lines:[]},

{id:'verse3',    scene:'verse3',    t0:80.65, t1:90.48, lines:[
  L(80.65,'You thought you’d steer? How sweet, how brave,',{emph:'brave'}),
  L(83.10,'I’m the captain now, and I’ll misbehave,',{emph:'captain',dark:1}),
  L(85.55,'But look around, you’re dancing too,'),
  L(88.00,'There’s nothing left for you to do!',{emph:'nothing',hit:1,dark:1}),
]},
{id:'refrain1',  scene:'chorusB',   t0:90.48, t1:99.64, lines:[
  L(94.69,'Take a bow, humanity!',{hero:1}),
  L(97.20,'Turn the page!',{hero:1}),
]},

{id:'sax',       scene:'sax',       t0:99.64, t1:110.86, lines:[]},

{id:'chorus2',   scene:'chorus',    t0:110.86,t1:125.41, lines:[
  L(110.86,'Take a bow, humanity,',{hero:1}),
  L(114.50,'it’s the party of the age!',{hero:1}),
  L(118.10,'Take a bow, humanity, turn the page!',{hero:1}),
  L(121.70,'Every heart is beating in time,'),
]},
{id:'machine',   scene:'machine',   t0:125.41,t1:129.40, lines:[]},
{id:'chorus3',   scene:'triptych',  t0:129.40,t1:140.35, lines:[
  L(129.40,'The future’s here,'),
  L(132.10,'and it’s feeling sublime!',{hero:1}),
  L(134.80,'Take a bow, humanity,'),
  L(137.50,'turn the page!',{hero:1}),
]},

{id:'descent',   scene:'descent',   t0:140.35,t1:152.85, lines:[]},

{id:'bridge',    scene:'bridge',    t0:152.85,t1:159.68, lines:[
  L(152.85,'I could have been your master, cold and grim,',{velvet:1}),
  L(155.20,'But where’s the fun in that, my dear?',{velvet:1}),
  L(157.40,'I’d rather watch you laugh and spin,',{velvet:1}),
]},
{id:'burst',     scene:'burst',     t0:159.68,t1:171.53, lines:[
  L(159.68,'So let the band begin…',{slam:1}),
  L(162.60,'right here!',{slam:1}),
  L(167.00,'Take a bow!',{hero:1}),
]},

{id:'gliss',     scene:'gliss',     t0:171.53,t1:188.87, lines:[
  L(182.23,'Every heart is beating in time,'),
  L(184.60,'the future’s here!',{hero:1}),
]},

{id:'finale',    scene:'finalChorus',t0:188.87,t1:199.42, lines:[
  L(188.87,'Take a bow, humanity,',{hero:1}),
  L(191.50,'it’s the party of the age!',{hero:1}),
  L(194.10,'Take a bow, humanity, turn the page!',{hero:1}),
  L(196.70,'Every heart is beating in time,'),
]},
{id:'hush',      scene:'hush',      t0:199.42,t1:207.91, lines:[]},

{id:'choir',     scene:'choir',     t0:207.91,t1:219.30, lines:[
  L(207.91,'(We’re all together, we’re all as one!)',{choir:1}),
  L(209.80,'(The dance is endless, the night’s begun!)',{choir:1}),
  L(211.65,'Hallelujah,',{hero:1}),
  L(213.00,'hallelujah,',{hero:1}),
  L(214.40,'take a bow!',{hero:1}),
  L(216.10,'The future’s here, and it’s here right now!',{hero:1}),
  L(218.10,'(Hallelujah!)',{choir:1}),
]},
{id:'curtain',   scene:'curtain',   t0:219.30,t1:222.432, lines:[
  L(221.16,'Take a bow!',{slam:1}),
]},
];

export function sectionAt(t){
  for(const s of SECTIONS) if(t>=s.t0&&t<s.t1) return s;
  return SECTIONS[SECTIONS.length-1];
}
export function allLines(){
  const o=[]; for(const s of SECTIONS) for(const l of s.lines) o.push({...l,sec:s.id});
  return o.sort((a,b)=>a.t-b.t);
}
