/**
 * Backdrop: illustrated, slowly moving scenery for story episodes, drawn as
 * layered SVG silhouettes (no image files). A scene asks for one with
 * `data.backdrop`:
 *   gurukul      dawn forest hermitage
 *   kurukshetra  battlefield at dusk
 *   palace       lamp-lit royal court at night
 *   cosmos       stars and a turning mandala, for the divine
 * Layers drift at different speeds for depth. The top and bottom are darkened
 * so the title and the captions stay readable.
 */
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

export type BackdropName = "gurukul" | "kurukshetra" | "palace" | "cosmos";

const W = 1080;
const H = 1920;

/** Deterministic pseudo-random in 0..1. */
const rnd = (i: number, salt = 1) => {
  const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
};

const Tree: React.FC<{ x: number; base: number; h: number; fill: string }> = ({ x, base, h, fill }) => (
  <g fill={fill}>
    <rect x={x - h * 0.035} y={base - h * 0.55} width={h * 0.07} height={h * 0.55} />
    <ellipse cx={x} cy={base - h * 0.62} rx={h * 0.3} ry={h * 0.26} />
    <ellipse cx={x - h * 0.2} cy={base - h * 0.48} rx={h * 0.2} ry={h * 0.17} />
    <ellipse cx={x + h * 0.21} cy={base - h * 0.5} rx={h * 0.21} ry={h * 0.18} />
    <ellipse cx={x + h * 0.03} cy={base - h * 0.82} rx={h * 0.2} ry={h * 0.17} />
  </g>
);

const Gurukul: React.FC<{ frame: number }> = ({ frame }) => {
  const drift = Math.sin(frame / 90) * 10;
  return (
    <>
      <defs>
        <linearGradient id="gk-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1A1040" />
          <stop offset="0.38" stopColor="#5B2A6E" />
          <stop offset="0.6" stopColor="#E0723E" />
          <stop offset="0.74" stopColor="#FFC56B" />
        </linearGradient>
        <radialGradient id="gk-sun">
          <stop offset="0" stopColor="#FFF4C2" />
          <stop offset="0.35" stopColor="#FFD166" stopOpacity="0.9" />
          <stop offset="1" stopColor="#FFB347" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#gk-sky)" />
      <circle cx={770} cy={1010 - frame * 0.05} r={330} fill="url(#gk-sun)" />
      <circle cx={770} cy={1010 - frame * 0.05} r={92} fill="#FFF1B8" />
      {[0, 1, 2, 3, 4].map((i) => (
        <path key={i} d="M0 0 q14 -12 28 0 q14 -12 28 0" stroke="#2A1638" strokeWidth={4} fill="none" transform={`translate(${((180 + i * 190 + frame * (0.5 + i * 0.12)) % 1300) - 110} ${640 + rnd(i) * 220 + Math.sin(frame / 14 + i) * 8}) scale(${0.6 + rnd(i, 2) * 0.5})`} />
      ))}
      <path d={`M${-40 + drift * 0.3} 1150 L160 930 L330 1080 L520 880 L700 1090 L900 940 L1140 1130 L1140 1300 L-40 1300 Z`} fill="#7A3B63" opacity={0.75} />
      <path d={`M${-40 + drift * 0.6} 1230 L120 1090 L300 1190 L470 1060 L680 1200 L860 1100 L1140 1220 L1140 1400 L-40 1400 Z`} fill="#4B2450" />
      <g transform={`translate(${drift} 0)`}>
        <Tree x={90} base={1330} h={520} fill="#2B1736" />
        <Tree x={1010} base={1340} h={600} fill="#2B1736" />
        <Tree x={300} base={1300} h={300} fill="#3A1F45" />
        {/* thatched hut */}
        <g fill="#24122E">
          <path d="M610 1210 L760 1105 L910 1210 Z" />
          <rect x={640} y={1210} width={240} height={110} />
        </g>
        <rect x={735} y={1245} width={50} height={75} fill="#FFB347" opacity={0.85} />
      </g>
      <defs>
        <linearGradient id="gk-ground" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#4A2552" />
          <stop offset="1" stopColor="#1A0D22" />
        </linearGradient>
        <radialGradient id="gk-fire">
          <stop offset="0" stopColor="#FFE9A8" />
          <stop offset="0.3" stopColor="#FF8A3D" stopOpacity="0.75" />
          <stop offset="1" stopColor="#FF8A3D" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect y={1300} width={W} height={H - 1300} fill="url(#gk-ground)" />
      {/* a pale path winding down from the hut */}
      <path d="M735 1320 Q700 1450 560 1560 Q380 1700 330 1920 L760 1920 Q740 1700 700 1580 Q760 1450 785 1320 Z" fill="#8A5A7A" opacity={0.45} />
      {/* the sacred fire, and a row of lamps along the path */}
      <circle cx={540} cy={1600} r={300 + Math.sin(frame / 4) * 22} fill="url(#gk-fire)" opacity={0.6} />
      <path d="M470 1650 h140 l-22 46 h-96 Z" fill="#3B1D2E" />
      {[0, 1, 2].map((i) => (
        <path key={i} d={`M${506 + i * 34} 1650 q${-18 + Math.sin(frame / 3 + i) * 10} ${-50 - i * 6} 0 ${-96 - Math.sin(frame / 2.4 + i * 2) * 26} q${18 + Math.sin(frame / 3.3 + i) * 10} ${46 + i * 6} 0 ${96 + Math.sin(frame / 2.4 + i * 2) * 26} Z`} fill={i === 1 ? "#FFE08A" : "#FF9A3D"} opacity={0.92} />
      ))}
      {[[250, 1480], [830, 1470], [170, 1700], [910, 1720], [300, 1860], [800, 1870]].map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y - 8} r={54 + Math.sin(frame / 5 + i * 1.7) * 8} fill="url(#gk-fire)" opacity={0.5} />
          <path d={`M${x - 16} ${y} h32 l-7 12 h-18 Z`} fill="#B5651D" />
          <ellipse cx={x} cy={y - 8} rx={5} ry={10 + Math.sin(frame / 3 + i) * 3} fill="#FFE9A8" />
        </g>
      ))}
      <g transform={`translate(${drift * 1.8} 0)`}>
        <Tree x={-30} base={1520} h={760} fill="#12091A" />
        <Tree x={1120} base={1540} h={820} fill="#12091A" />
      </g>
    </>
  );
};

const Kurukshetra: React.FC<{ frame: number }> = ({ frame }) => {
  const drift = Math.sin(frame / 80) * 8;
  return (
    <>
      <defs>
        <linearGradient id="kk-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1C0710" />
          <stop offset="0.4" stopColor="#7A1420" />
          <stop offset="0.62" stopColor="#E0531F" />
          <stop offset="0.72" stopColor="#FFB45E" />
        </linearGradient>
        <radialGradient id="kk-sun">
          <stop offset="0" stopColor="#FFE9A8" />
          <stop offset="0.5" stopColor="#FF8A3D" stopOpacity="0.85" />
          <stop offset="1" stopColor="#E0531F" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#kk-sky)" />
      <circle cx={540} cy={1180} r={520} fill="url(#kk-sun)" />
      <circle cx={540} cy={1180} r={210} fill="#FFD98A" />
      {/* far army: a line of spears and banners */}
      <g transform={`translate(${drift * 0.5} 0)`} fill="#3A0C14" stroke="#3A0C14">
        {Array.from({ length: 46 }).map((_, i) => {
          const x = i * 24 + rnd(i) * 10;
          const h = 60 + rnd(i, 3) * 70;
          return <line key={i} x1={x} y1={1290} x2={x + (rnd(i, 5) - 0.5) * 8} y2={1290 - h} strokeWidth={3} />;
        })}
        {[110, 330, 560, 790, 980].map((x, i) => (
          <path key={x} d={`M${x} 1290 L${x} ${1120 - i * 6} l${52 + Math.sin(frame / 9 + i) * 8} ${16 + Math.sin(frame / 7 + i) * 5} l${-52 - Math.sin(frame / 9 + i) * 8} 18 Z`} strokeWidth={4} />
        ))}
        <rect x={-40} y={1285} width={W + 80} height={80} />
      </g>
      {/* chariots */}
      <g transform={`translate(${drift * 1.2} 0)`} fill="#1E060B" stroke="#1E060B">
        {[150, 880].map((x, i) => (
          <g key={x} transform={`translate(${x} 1345) scale(${i ? -1 : 1} 1)`}>
            <circle r={62} fill="none" strokeWidth={10} />
            {[0, 1, 2, 3, 4, 5].map((s) => (
              <line key={s} x1={0} y1={0} x2={Math.cos((s * Math.PI) / 3 + frame / 40) * 62} y2={Math.sin((s * Math.PI) / 3 + frame / 40) * 62} strokeWidth={5} />
            ))}
            <path d="M-70 -40 L90 -40 L120 -150 L-40 -150 Z" />
            <path d="M40 -150 L40 -330 l70 22 l-70 24" />
          </g>
        ))}
        <rect x={-40} y={1385} width={W + 80} height={H - 1385} />
      </g>
      {/* dust */}
      {Array.from({ length: 26 }).map((_, i) => (
        <circle key={i} cx={(rnd(i) * 1200 + frame * (0.6 + rnd(i, 2))) % 1160 - 40} cy={1180 + rnd(i, 4) * 260 + Math.sin(frame / 20 + i) * 10} r={18 + rnd(i, 6) * 46} fill="#FFB45E" opacity={0.05 + rnd(i, 7) * 0.06} />
      ))}
    </>
  );
};

const Palace: React.FC<{ frame: number }> = ({ frame }) => {
  const lamps = [180, 540, 900];
  return (
    <>
      <defs>
        <linearGradient id="pl-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0D0A2A" />
          <stop offset="0.6" stopColor="#2A1452" />
          <stop offset="1" stopColor="#3D1A4A" />
        </linearGradient>
        <radialGradient id="pl-lamp">
          <stop offset="0" stopColor="#FFE7A3" />
          <stop offset="0.3" stopColor="#FFB627" stopOpacity="0.7" />
          <stop offset="1" stopColor="#FFB627" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#pl-wall)" />
      {/* arches between pillars */}
      {[0, 1, 2].map((i) => (
        <path key={i} d={`M${60 + i * 360} 1320 L${60 + i * 360} 820 Q${60 + i * 360} 600 ${200 + i * 360} 560 Q${340 + i * 360} 600 ${340 + i * 360} 820 L${340 + i * 360} 1320 Z`} fill="#150B36" stroke="#C9972B" strokeWidth={5} opacity={0.9} />
      ))}
      {[0, 1, 2, 3].map((i) => (
        <g key={i} fill="#3A2168">
          <rect x={10 + i * 360 - 30} y={500} width={80} height={840} />
          <rect x={10 + i * 360 - 46} y={480} width={112} height={34} fill="#C9972B" />
          <rect x={10 + i * 360 - 46} y={1320} width={112} height={34} fill="#C9972B" />
        </g>
      ))}
      {lamps.map((x, i) => {
        const flick = 0.82 + Math.sin(frame / 5 + i * 2.1) * 0.08 + Math.sin(frame / 2.3 + i) * 0.04;
        return (
          <g key={x}>
            <line x1={x + 20} y1={480} x2={x + 20} y2={690} stroke="#C9972B" strokeWidth={4} />
            <circle cx={x + 20} cy={730} r={230 * flick} fill="url(#pl-lamp)" />
            <path d={`M${x - 12} 700 h64 l-14 44 h-36 Z`} fill="#C9972B" />
            <ellipse cx={x + 20} cy={690} rx={11} ry={20 * flick} fill="#FFF1B8" />
          </g>
        );
      })}
      {/* patterned floor */}
      <rect y={1340} width={W} height={H - 1340} fill="#1A0D2E" />
      {Array.from({ length: 9 }).map((_, i) => (
        <line key={i} x1={540 + (i - 4) * 70} y1={1340} x2={540 + (i - 4) * 320} y2={H} stroke="#C9972B" strokeWidth={2} opacity={0.25} />
      ))}
      {[1420, 1540, 1700].map((y) => (
        <line key={y} x1={0} y1={y} x2={W} y2={y} stroke="#C9972B" strokeWidth={2} opacity={0.18} />
      ))}
    </>
  );
};

const Cosmos: React.FC<{ frame: number }> = ({ frame }) => (
  <>
    <defs>
      <radialGradient id="cs-bg" cx="0.5" cy="0.45" r="0.8">
        <stop offset="0" stopColor="#3B1E7A" />
        <stop offset="0.5" stopColor="#170B3D" />
        <stop offset="1" stopColor="#05030F" />
      </radialGradient>
      <radialGradient id="cs-core">
        <stop offset="0" stopColor="#FFE7A3" stopOpacity="0.9" />
        <stop offset="1" stopColor="#FFB627" stopOpacity="0" />
      </radialGradient>
    </defs>
    <rect width={W} height={H} fill="url(#cs-bg)" />
    {Array.from({ length: 90 }).map((_, i) => (
      <circle key={i} cx={rnd(i) * W} cy={rnd(i, 2) * H} r={1 + rnd(i, 3) * 2.6} fill="#FFF7E6" opacity={0.35 + 0.5 * Math.abs(Math.sin(frame / 22 + i))} />
    ))}
    <circle cx={540} cy={880} r={420} fill="url(#cs-core)" opacity={0.5} />
    {[330, 250, 170].map((r, ring) => (
      <g key={r} transform={`rotate(${(frame * (ring % 2 ? -0.25 : 0.18)) % 360} 540 880)`} stroke="#FFC83D" fill="none" opacity={0.5 - ring * 0.08}>
        <circle cx={540} cy={880} r={r} strokeWidth={3} />
        {Array.from({ length: 16 }).map((_, i) => {
          const a = (i / 16) * Math.PI * 2;
          return <path key={i} d={`M${540 + Math.cos(a) * r} ${880 + Math.sin(a) * r} Q${540 + Math.cos(a + 0.2) * (r + 46)} ${880 + Math.sin(a + 0.2) * (r + 46)} ${540 + Math.cos(a + 0.39) * r} ${880 + Math.sin(a + 0.39) * r}`} strokeWidth={3} />;
        })}
      </g>
    ))}
  </>
);

export const Backdrop: React.FC<{ name: BackdropName }> = ({ name }) => {
  const frame = useCurrentFrame();
  const scene = name === "kurukshetra" ? <Kurukshetra frame={frame} /> : name === "palace" ? <Palace frame={frame} /> : name === "cosmos" ? <Cosmos frame={frame} /> : <Gurukul frame={frame} />;
  return (
    <AbsoluteFill>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
        {scene}
        <defs>
          <linearGradient id="bd-scrim" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#07030F" stopOpacity="0.78" />
            <stop offset="0.3" stopColor="#07030F" stopOpacity="0.1" />
            <stop offset="0.58" stopColor="#07030F" stopOpacity="0.05" />
            <stop offset="0.66" stopColor="#07030F" stopOpacity="0.42" />
            <stop offset="1" stopColor="#07030F" stopOpacity="0.55" />
          </linearGradient>
        </defs>
        <rect width={W} height={H} fill="url(#bd-scrim)" />
      </svg>
    </AbsoluteFill>
  );
};
