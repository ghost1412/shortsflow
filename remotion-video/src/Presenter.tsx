// A drawn presenter that talks with the narration: a person, a cat, a dog or a robot, built from parts (engine/avatars.py holds the ready-made
// ones and checks home-made ones). The mouth follows the words' timings (letters -> mouth shapes spread over each word); it blinks, lifts its
// brows on long words, nods while talking and sways when quiet. `presenterRect` is the ONE place that says where the card sits, so the scenes
// and the cover can keep out of it (they read it through `usePresenterRoom`).
import React, { createContext, useContext, useMemo } from "react";
import { AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig } from "remotion";
import { z } from "zod";

const hex = z.string().regex(/^#[0-9a-fA-F]{6}$/);
export const avatarSchema = z.object({
  kind: z.enum(["human", "cat", "dog", "robot"]).default("human"),
  name: z.string().default(""),                     // shown on the card's tag; empty shows no tag
  skin: hex.default("#f1c3a0"),                     // skin, fur or the robot's body
  hair: z.enum(["short", "side", "long", "bob", "bun", "curly", "ponytail", "bald"]).default("short"),
  hairColor: hex.default("#2b1d15"),
  eyeColor: hex.default("#3b6fd8"),
  beard: z.enum(["none", "stubble", "full", "moustache"]).default("none"),
  glasses: z.enum(["none", "round", "square"]).default("none"),
  lashes: z.boolean().default(false),
  lips: hex.default("#b0505a"),
  outfit: hex.default("#ff8a3d"),
  pattern: z.enum(["plain", "tabby", "patch"]).default("plain"),   // animals: stripes or an eye patch
  furLight: hex.default("#fff4e8"),                 // animals: muzzle, chest and inner ears
});
export type Avatar = z.infer<typeof avatarSchema>;
type Word = { word: string; start: number; end: number };

// --- where the card goes ------------------------------------------------------------------------------------------------------------------
// Landscape: a column on the right, standing on the caption zone. Portrait: the bottom-right corner, above the caption zone. The scene gives up
// exactly that room (`room`), so content never runs under the card.
export type PresenterRect = { left: number; top: number; width: number; height: number; room: { right: number; bottom: number } };
export const presenterRect = (u: number, w: number, h: number, captionTop: number): PresenterRect => {
  const portrait = h > w;
  const width = (portrait ? 380 : 340) * u, height = (portrait ? 440 : 400) * u, margin = (portrait ? 44 : 56) * u, gap = 24 * u;
  const top = h - captionTop - gap - height;
  return { left: w - margin - width, top, width, height,
           room: portrait ? { right: 0, bottom: height + gap } : { right: width + margin * 0.6, bottom: 0 } };
};
export const PresenterRoom = createContext<{ right: number; bottom: number }>({ right: 0, bottom: 0 });
export const usePresenterRoom = () => useContext(PresenterRoom);

// --- mouth shapes -------------------------------------------------------------------------------------------------------------------------
type Shape = { w: number; o: number; r: number; teeth: number; tongue: number; bite?: boolean; up?: boolean };
const SH: Record<string, Shape> = {
  X: { w: 20, o: 1, r: 0, teeth: 0, tongue: 0 },          // rest
  M: { w: 18, o: 0, r: 0, teeth: 0, tongue: 0 },          // m b p: lips closed
  C: { w: 17, o: 8, r: 0.2, teeth: 1, tongue: 0 },        // most consonants
  A: { w: 19, o: 19, r: 0.45, teeth: 1, tongue: 1 },
  E: { w: 23, o: 10, r: 0.1, teeth: 1, tongue: 0 },
  O: { w: 12, o: 16, r: 1, teeth: 0, tongue: 1 },
  U: { w: 8, o: 9, r: 1, teeth: 0, tongue: 0 },
  F: { w: 19, o: 5, r: 0.1, teeth: 1, tongue: 0, bite: true },
  L: { w: 17, o: 13, r: 0.4, teeth: 1, tongue: 1, up: true },
};
const LETTER: Record<string, string> = {};
([["mbp", "M"], ["fv", "F"], ["ai", "A"], ["e", "E"], ["o", "O"], ["uwq", "U"], ["lt", "L"]] as const).forEach(([ls, s]) => [...ls].forEach((c) => (LETTER[c] = s)));

/** [(seconds, shape)] for the whole video: each word's letters as mouth shapes, repeats collapsed, spread over the word; rest between words. */
export const visemes = (words: Word[]): [number, string][] => {
  const out: [number, string][] = [[0, "X"]];
  for (const w of words) {
    const dur = Math.max(0.05, w.end - w.start);
    const shapes: string[] = [];
    for (const ch of w.word.toLowerCase()) {
      if (!/[a-z]/.test(ch)) continue;
      const s = LETTER[ch] ?? "C";
      if (shapes[shapes.length - 1] !== s) shapes.push(s);
    }
    const kept = shapes.slice(0, Math.max(1, Math.floor(dur / 0.07)));
    const list = kept.length ? kept : ["C"];
    list.forEach((s, i) => out.push([w.start + (i * dur) / list.length, s]));
    out.push([w.end, "X"]);
  }
  return out;
};
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
const shapeAt = (vis: [number, string][], t: number): Shape => {
  let lo = 0, hi = vis.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (vis[mid][0] <= t) lo = mid; else hi = mid - 1; }
  const cur = SH[vis[lo][1]], prev = SH[vis[Math.max(0, lo - 1)][1]];
  const k = Math.min(1, (t - vis[lo][0]) / 0.06);
  return { w: lerp(prev.w, cur.w, k), o: lerp(prev.o, cur.o, k), r: lerp(prev.r, cur.r, k), teeth: lerp(prev.teeth, cur.teeth, k),
           tongue: lerp(prev.tongue, cur.tongue, k), bite: cur.bite, up: cur.up };
};

// --- parts --------------------------------------------------------------------------------------------------------------------------------
const shade = (c: string, f: number) => {          // f < 0 darker, f > 0 lighter
  const n = parseInt(c.slice(1), 16), ch = [n >> 16, (n >> 8) & 255, n & 255].map((v) => Math.round(f < 0 ? v * (1 + f) : v + (255 - v) * f));
  return "#" + ch.map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0")).join("");
};

const HumanMouth: React.FC<{ m: Shape; lips: string; cx?: number; cy?: number; id: string }> = ({ m, lips, cx = 150, cy = 214, id }) => {
  const { w, o, r } = m;
  if (o < 1.5) return <path d={`M${cx - w} ${cy} Q${cx} ${cy + 6} ${cx + w} ${cy}`} stroke={lips} strokeWidth={5} strokeLinecap="round" fill="none" />;
  const top = cy - o * (0.35 + 0.15 * r), bot = cy + o * (0.65 - 0.15 * r), side = w * (1 - 0.15 * r);
  const d = `M${cx - side} ${cy} C${cx - side} ${top} ${cx - w * 0.4} ${top - 2} ${cx} ${top - 1} C${cx + w * 0.4} ${top - 2} ${cx + side} ${top} ${cx + side} ${cy} `
          + `C${cx + side} ${bot} ${cx + w * 0.45} ${bot + 3} ${cx} ${bot + 3} C${cx - w * 0.45} ${bot + 3} ${cx - side} ${bot} ${cx - side} ${cy} Z`;
  return (
    <g>
      <clipPath id={id}><path d={d} /></clipPath>
      <path d={d} fill="#5a1b26" />
      <g clipPath={`url(#${id})`}>
        {m.teeth > 0.3 && <rect x={cx - w} y={top - 4} width={2 * w} height={6 + o * 0.12} rx={2} fill="#fff" opacity={Math.min(1, m.teeth)} />}
        {m.tongue > 0.3 && <ellipse cx={cx} cy={m.up ? top + o * 0.45 : bot + 2} rx={w * 0.7} ry={o * 0.38} fill="#e86a77" opacity={Math.min(1, m.tongue)} />}
      </g>
      <path d={d} stroke={lips} strokeWidth={3.5} fill="none" />
      {m.bite && <path d={`M${cx - w * 0.8} ${bot - 1} Q${cx} ${bot - 5} ${cx + w * 0.8} ${bot - 1}`} stroke={lips} strokeWidth={5} strokeLinecap="round" fill="none" />}
    </g>
  );
};

const Eyes: React.FC<{ a: Avatar; blink: number; look: number; y?: number; gap?: number; cat?: boolean }> = ({ a, blink, look, y = 156, gap = 30, cat }) => (
  <g>
    {[-1, 1].map((s) => (
      <g key={s} transform={`translate(${150 + s * gap} ${y})`}>
        <ellipse rx={cat ? 15 : 13} ry={(cat ? 14 : 12) * (1 - blink * 0.95)} fill="#fff" />
        {blink < 0.6 && (cat
          ? <><ellipse cx={look} rx={10} ry={12 * (1 - blink)} fill={a.eyeColor} /><ellipse cx={look} rx={3} ry={10 * (1 - blink)} fill="#0d1220" /><circle cx={look + 3} cy={-4} r={2.4} fill="#fff" /></>
          : <><circle cx={look} r={7.5} fill={a.eyeColor} /><circle cx={look} r={3.6} fill="#0d1220" /><circle cx={look + 2.6} cy={-3} r={2} fill="#fff" /></>)}
        {a.lashes && blink < 0.6 && <path d={`M${13 * s} ${-6} l${7 * s} ${-6} M${8 * s} ${-10} l${4 * s} ${-7}`} stroke="#1a120d" strokeWidth={2.6} strokeLinecap="round" />}
      </g>
    ))}
  </g>
);

const Glasses: React.FC<{ kind: Avatar["glasses"] }> = ({ kind }) => {
  if (kind === "none") return null;
  const lens = (x: number) => kind === "round" ? <circle cx={x} cy={157} r={19} /> : <rect x={x - 21} y={142} width={42} height={30} rx={7} />;
  return <g fill="rgba(200,230,255,0.12)" stroke="#1c1f2b" strokeWidth={4}>{lens(120)}{lens(180)}<path d="M139 155 Q150 149 161 155" fill="none" /></g>;
};

const HairBack: React.FC<{ a: Avatar }> = ({ a }) => {
  const c = a.hairColor;
  if (a.hair === "long") return <path d="M76 140 C70 70 230 70 224 140 L236 300 C200 318 100 318 64 300 Z" fill={c} />;
  if (a.hair === "bob") return <path d="M74 140 C70 70 230 70 226 140 L230 236 C206 250 94 250 70 236 Z" fill={c} />;
  if (a.hair === "ponytail") return <path d="M214 120 C262 130 262 220 236 262 C226 230 222 190 206 160 Z" fill={c} />;
  return null;
};
const HairFront: React.FC<{ a: Avatar }> = ({ a }) => {
  const c = a.hairColor, dark = shade(c, -0.3);
  switch (a.hair) {
    case "bald": return <path d="M80 150 C80 132 86 120 92 116 M220 150 C220 132 214 120 208 116" stroke={c} strokeWidth={9} strokeLinecap="round" fill="none" />;
    case "side": return <path d="M76 150 C68 88 108 52 156 52 C206 54 236 96 224 152 C220 126 210 110 194 102 C160 120 118 102 96 96 C86 112 80 128 76 150 Z" fill={c} />;
    case "curly": return <g fill={c}>{[[90, 110], [104, 86], [128, 70], [154, 64], [180, 70], [202, 86], [214, 110], [82, 136], [220, 136], [116, 92], [168, 88], [142, 82]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={20} />)}</g>;
    case "bun": return <g fill={c}><circle cx={150} cy={50} r={26} /><path d="M76 150 C70 92 104 56 150 56 C196 56 230 92 224 150 C214 116 190 98 150 96 C110 98 86 116 76 150 Z" /></g>;
    case "long": case "bob": case "ponytail":
      return <path d="M76 156 C70 92 104 56 150 56 C196 56 230 92 224 156 C216 120 196 104 170 100 C150 116 116 118 92 110 C84 124 78 140 76 156 Z" fill={c} />;
    default: return <g><path d="M76 150 C70 92 104 52 152 52 C204 52 234 92 224 150 C214 120 196 100 166 96 C142 112 108 116 86 112 C80 124 78 136 76 150 Z" fill={c} /><path d="M120 70 Q150 60 182 72" stroke={dark} strokeWidth={3} fill="none" opacity={0.5} /></g>;
  }
};
const Beard: React.FC<{ a: Avatar }> = ({ a }) => {
  const c = a.hairColor;
  if (a.beard === "stubble") return <path d="M96 196 C104 240 196 240 204 196 C196 226 104 226 96 196 Z" fill={c} opacity={0.28} />;
  if (a.beard === "full") return <path d="M84 176 C86 236 116 262 150 262 C184 262 214 236 216 176 C206 200 196 206 186 204 C176 196 124 196 114 204 C104 206 94 200 84 176 Z" fill={c} />;
  if (a.beard === "moustache") return <path d="M126 202 C136 194 146 196 150 200 C154 196 164 194 174 202 C164 206 156 206 150 203 C144 206 136 206 126 202 Z" fill={c} />;
  return null;
};

const Human: React.FC<{ a: Avatar; m: Shape; blink: number; look: number; lift: number; id: string }> = ({ a, m, blink, look, lift, id }) => {
  const skin = a.skin, dark = shade(skin, -0.12);
  return (
    <g>
      <HairBack a={a} />
      <ellipse cx={80} cy={168} rx={13} ry={20} fill={dark} />
      <ellipse cx={220} cy={168} rx={13} ry={20} fill={dark} />
      <path d="M150 62 C204 62 222 106 222 160 C222 214 190 250 150 250 C110 250 78 214 78 160 C78 106 96 62 150 62 Z" fill={skin} />
      <ellipse cx={112} cy={192} rx={14} ry={8} fill="#f29b8a" opacity={0.3} />
      <ellipse cx={188} cy={192} rx={14} ry={8} fill="#f29b8a" opacity={0.3} />
      <HairFront a={a} />
      <g transform={`translate(0 ${-lift})`} stroke={shade(a.hairColor, -0.1)} strokeWidth={6} strokeLinecap="round" fill="none">
        <path d="M104 132 Q120 124 136 131" /><path d="M164 131 Q180 124 196 132" />
      </g>
      <Eyes a={a} blink={blink} look={look} />
      <path d="M150 166 Q144 186 150 192 Q156 194 160 190" stroke={shade(skin, -0.25)} strokeWidth={3.5} fill="none" strokeLinecap="round" />
      <Beard a={a} />
      <HumanMouth m={m} lips={a.lips} id={id} />
      <Glasses kind={a.glasses} />
    </g>
  );
};

const AnimalMouth: React.FC<{ m: Shape; cx: number; cy: number; dog?: boolean; id: string }> = ({ m, cx, cy, dog, id }) => {
  const o = m.o * (dog ? 1.1 : 0.9), w = 10 + m.w * 0.45;
  return (
    <g>
      {o > 2 && (
        <g>
          <clipPath id={id}><ellipse cx={cx} cy={cy + o * 0.55} rx={w} ry={o * 0.7} /></clipPath>
          <ellipse cx={cx} cy={cy + o * 0.55} rx={w} ry={o * 0.7} fill="#4a1520" />
          <ellipse clipPath={`url(#${id})`} cx={cx} cy={cy + o * 1.05} rx={w * 0.75} ry={o * 0.45} fill="#ec7181" />
        </g>
      )}
      <path d={`M${cx - 18} ${cy - 2} Q${cx - 9} ${cy + 8} ${cx} ${cy - 2} Q${cx + 9} ${cy + 8} ${cx + 18} ${cy - 2}`} stroke="#3a2420" strokeWidth={3.5} fill="none" strokeLinecap="round" />
    </g>
  );
};

const Cat: React.FC<{ a: Avatar; m: Shape; blink: number; look: number; lift: number; twitch: number; id: string }> = ({ a, m, blink, look, lift, twitch, id }) => {
  const fur = a.skin, light = a.furLight, dark = shade(fur, -0.3);
  return (
    <g>
      <g transform={`rotate(${-twitch * 8} 92 98)`}><path d="M74 128 L84 46 L136 96 Z" fill={fur} /><path d="M86 112 L91 66 L120 94 Z" fill={light} opacity={0.85} /></g>
      <g transform={`rotate(${twitch * 3} 208 98)`}><path d="M226 128 L216 46 L164 96 Z" fill={fur} /><path d="M214 112 L209 66 L180 94 Z" fill={light} opacity={0.85} /></g>
      <ellipse cx={150} cy={164} rx={86} ry={78} fill={fur} />
      {a.pattern === "tabby" && <g stroke={dark} strokeWidth={7} strokeLinecap="round" fill="none"><path d="M150 92 V116" /><path d="M128 96 L134 116" /><path d="M172 96 L166 116" /><path d="M66 160 L88 164" /><path d="M234 160 L212 164" /></g>}
      {a.pattern === "patch" && <ellipse cx={186} cy={150} rx={30} ry={26} fill={dark} />}
      <ellipse cx={150} cy={204} rx={44} ry={30} fill={light} />
      <g transform={`translate(0 ${-lift})`} stroke={dark} strokeWidth={4} strokeLinecap="round"><path d="M110 128 L130 132" /><path d="M190 128 L170 132" /></g>
      <Eyes a={a} blink={blink} look={look} y={154} gap={34} cat />
      <path d="M142 186 L158 186 L150 196 Z" fill="#e8707f" />
      <AnimalMouth m={m} cx={150} cy={198} id={id} />
      <g stroke="#ffffff" strokeWidth={2} opacity={0.85}><path d="M104 196 L62 188" /><path d="M104 204 L60 206" /><path d="M196 196 L238 188" /><path d="M196 204 L240 206" /></g>
    </g>
  );
};

const Dog: React.FC<{ a: Avatar; m: Shape; blink: number; look: number; lift: number; twitch: number; id: string }> = ({ a, m, blink, look, lift, twitch, id }) => {
  const fur = a.skin, light = a.furLight, dark = shade(fur, -0.35);
  return (
    <g>
      <ellipse cx={150} cy={160} rx={80} ry={84} fill={fur} />
      {a.pattern === "patch" && <ellipse cx={118} cy={150} rx={28} ry={30} fill={dark} />}
      <g transform={`rotate(${twitch * 6} 82 104)`}><path d="M84 96 C50 96 40 150 56 196 C70 200 84 180 92 150 Z" fill={dark} /></g>
      <g transform={`rotate(${-twitch * 4} 218 104)`}><path d="M216 96 C250 96 260 150 244 196 C230 200 216 180 208 150 Z" fill={dark} /></g>
      <ellipse cx={150} cy={206} rx={50} ry={36} fill={light} />
      <g transform={`translate(0 ${-lift})`} stroke={dark} strokeWidth={5} strokeLinecap="round"><path d="M106 124 Q118 118 132 124" /><path d="M168 124 Q182 118 194 124" /></g>
      <Eyes a={a} blink={blink} look={look} y={150} gap={30} />
      <ellipse cx={150} cy={186} rx={16} ry={11} fill="#20161a" /><ellipse cx={145} cy={182} rx={5} ry={3} fill="#fff" opacity={0.6} />
      <AnimalMouth m={m} cx={150} cy={202} dog id={id} />
    </g>
  );
};

const Robot: React.FC<{ a: Avatar; m: Shape; blink: number; look: number; t: number; accent: string }> = ({ a, m, blink, look, t, accent }) => {
  const body = a.skin, glow = a.eyeColor;
  const bars = 7, open = m.o / 19;
  return (
    <g>
      <line x1={150} y1={76} x2={150} y2={46} stroke={shade(body, -0.3)} strokeWidth={6} />
      <circle cx={150} cy={40} r={10} fill={accent} opacity={0.55 + 0.45 * Math.abs(Math.sin(t * 3))} />
      <rect x={70} y={76} width={160} height={164} rx={36} fill={body} />
      <rect x={58} y={136} width={16} height={46} rx={6} fill={shade(body, -0.25)} /><rect x={226} y={136} width={16} height={46} rx={6} fill={shade(body, -0.25)} />
      <rect x={88} y={100} width={124} height={118} rx={24} fill="#0b1020" />
      {[-1, 1].map((s) => <ellipse key={s} cx={150 + s * 28 + look} cy={140} rx={12} ry={14 * (1 - blink * 0.9)} fill={glow} opacity={0.95} />)}
      {Array.from({ length: bars }, (_, i) => {
        const mid = (bars - 1) / 2, k = 1 - Math.abs(i - mid) / (mid + 1);
        const hgt = 3 + open * 26 * k * (0.75 + 0.25 * Math.sin(t * 20 + i));
        return <rect key={i} x={114 + i * 11} y={190 - hgt / 2} width={7} height={hgt} rx={3} fill={glow} />;
      })}
    </g>
  );
};

// --- the card -----------------------------------------------------------------------------------------------------------------------------
export const Presenter: React.FC<{ avatar: Avatar; words: Word[]; rect: PresenterRect; accent: string; card: string; line: string; font: string }> = ({ avatar, words, rect, accent, card, line, font }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const a = avatarSchema.parse(avatar);                 // the renderer may hand over props without the schema defaults
  const vis = useMemo(() => visemes(words), [words]);
  const m = shapeAt(vis, t);
  const talking = words.some((w) => t >= w.start - 0.05 && t <= w.end + 0.15);
  const word = words.find((w) => t >= w.start && t < w.start + 0.5);
  const lift = word && word.word.replace(/[^a-z]/gi, "").length > 6 ? Math.max(0, 1 - (t - word.start) / 0.5) * 6 : 0;
  // a blink every 2.8-4.4 s, chosen from a fixed seed so every render is the same
  let blink = 0, at = 0.9, n = 0;
  while (at < t + 0.2 && n < 2000) { if (t >= at && t < at + 0.14) blink = Math.sin(((t - at) / 0.14) * Math.PI); at += 2.8 + random(`blink${n++}`) * 1.6; }
  const look = Math.sin(t * 0.45) > 0.6 ? -3 : 0;
  const twitch = Math.max(0, Math.sin(t * 0.9) - 0.92) * 12;
  const sway = talking ? 1 : 0.4;
  const rot = Math.sin(t * 1.7) * 2.2 * sway + Math.sin(t * 0.6) * 1.2;
  const dy = (talking ? Math.abs(Math.sin(t * 5.2)) * 2.4 : 0) + Math.sin(t * 1.1) * 1.2;
  const id = `pm${frame}`;
  const enterK = interpolate(frame, [0, 14], [0, 1], { extrapolateRight: "clamp" });
  const outfit = a.kind === "robot" ? shade(a.skin, -0.2) : a.kind === "human" ? a.outfit : a.skin;
  const s = rect.width / 330;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", left: rect.left, top: rect.top, width: rect.width, height: rect.height, borderRadius: 28 * s, overflow: "hidden",
                    background: `linear-gradient(180deg, ${accent}2e 0%, ${card} 70%)`, border: `1px solid ${line}`, boxShadow: `0 ${18 * s}px ${50 * s}px rgba(0,0,0,0.35)`,
                    opacity: enterK, transform: `translateY(${(1 - enterK) * 30 * s}px)` }}>
        <svg width={rect.width} height={rect.height * 0.97} viewBox="0 0 300 354" style={{ position: "absolute", left: 0, bottom: 0 }}>
          <g transform={`translate(0 ${Math.sin(t * 1.1) * 1.4})`}>
            <path d="M40 354 C48 290 96 262 150 262 C204 262 252 290 260 354 Z" fill={outfit} />
            {a.kind === "human" && <path d="M122 262 L150 300 L178 262 Z" fill="#fff" opacity={0.9} />}
            {(a.kind === "cat" || a.kind === "dog") && <path d="M112 270 C120 320 180 320 188 270 Z" fill={a.furLight} />}
            {a.kind === "robot" && <circle cx={150} cy={308} r={14} fill={accent} opacity={0.8} />}
            {a.kind === "human" && <rect x={132} y={228} width={36} height={42} rx={14} fill={shade(a.skin, -0.12)} />}
          </g>
          <g transform={`rotate(${rot} 150 240) translate(0 ${dy})`}>
            {a.kind === "human" && <Human a={a} m={m} blink={blink} look={look} lift={lift} id={id} />}
            {a.kind === "cat" && <Cat a={a} m={m} blink={blink} look={look} lift={lift} twitch={twitch} id={id} />}
            {a.kind === "dog" && <Dog a={a} m={m} blink={blink} look={look} lift={lift} twitch={twitch} id={id} />}
            {a.kind === "robot" && <Robot a={a} m={m} blink={blink} look={look} t={t} accent={accent} />}
          </g>
        </svg>
        {a.name && <div style={{ position: "absolute", left: 16 * s, bottom: 14 * s, fontFamily: font, fontSize: 15 * s, fontWeight: 800, letterSpacing: 1.2 * s,
                                 background: accent, color: "#111", padding: `${5 * s}px ${11 * s}px`, borderRadius: 8 * s, textTransform: "uppercase" }}>{a.name}</div>}
      </div>
    </AbsoluteFill>
  );
};

// A card on its own, for the builder's preview in the app: the presenter says a few words (no sound) so the mouth, blinks and nods show.
export const presenterCardSchema = z.object({
  avatar: avatarSchema,
  words: z.array(z.object({ word: z.string(), start: z.number(), end: z.number() })).default([]),
  accent: hex.default("#00e5a8"),
});
export const PresenterCard: React.FC<z.infer<typeof presenterCardSchema>> = ({ avatar, words, accent }) => {
  const { width, height } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: "linear-gradient(180deg, #12294d 0%, #07101f 100%)" }}>
      <Presenter avatar={avatar} words={words} rect={{ left: 0, top: 0, width, height, room: { right: 0, bottom: 0 } }} accent={accent}
                 card="rgba(16,30,54,0.82)" line="rgba(255,255,255,0.12)" font='"Segoe UI", Arial, sans-serif' />
    </AbsoluteFill>
  );
};
