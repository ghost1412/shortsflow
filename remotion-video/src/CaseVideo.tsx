// "CaseVideo": a sectioned explainer. Every section of the script is one scene (timeline, flow, counters, checklist, terminal, quote)
// drawn from its on-screen labels, over a themed background, with word-timed captions. No custom fonts (a font load stalled the CI
// renderer before), no stock footage: everything is drawn, so a run needs no key and no download.
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AbsoluteFill, Audio, Img, Loop, OffthreadVideo, Sequence, continueRender, delayRender, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import katex from "katex";
import { z } from "zod";

export const CASE_THEMES = ["dark", "clean", "warm", "neon", "newsroom", "blueprint", "terminal", "editorial", "midnight"] as const;
export const CASE_SCENES = ["timeline", "flow", "counters", "checklist", "terminal", "quote", "equation", "compare", "chart", "animation", "diagram"] as const;

export const caseVideoSchema = z.object({
  title: z.string().default("Explainer"),
  theme: z.enum(CASE_THEMES).default("dark"),
  accent: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  audioUrl: z.string().optional(),
  bgMusicUrl: z.string().optional(),
  bgMusicVolume: z.number().default(0.12),
  introSeconds: z.number().default(2.5),
  hook: z.string().default(""),               // one gripping line shown big on the cover card (the title becomes a small label above it)
  outroSeconds: z.number().default(3),
  verified: z.boolean().default(true),
  removedClaims: z.number().default(0),         // sentences the check removed because the sources do not hold them
  sources: z.array(z.string()).default([]),
  captionsOff: z.boolean().default(false),
  sections: z.array(z.object({
    title: z.string(),
    scene: z.enum(CASE_SCENES).default("quote"),
    labels: z.array(z.string()).default([]),
    sourceLabels: z.array(z.string()).default([]),   // where this section's facts come from, shown as a small chip
    footage: z.array(z.object({ src: z.string(), seconds: z.number().default(10), kind: z.enum(["video", "image"]).default("video") })).default([]),   // stock clips, one per beat, shown behind the scene
    beats: z.array(z.tuple([z.number(), z.number()])).default([]),                       // seconds after the section starts: a new picture at each
    clip: z.string().optional(),                // a rendered animation (Manim) drawn for this section, shown instead of the plain scene
    diagram: z.string().optional(),             // Mermaid source (any diagram type), drawn by Mermaid's own layout and revealed step by step
    clipRate: z.number().default(1),
    clipAspect: z.number().default(16 / 9),     // width / height of the clip: older clips are 16:9, the landscape panel clips are wider
    cues: z.array(z.number()).default([]),     // seconds after the section starts at which each label is spoken
    start: z.number(),
    end: z.number(),
  })).default([]),
  words: z.array(z.object({ word: z.string(), start: z.number(), end: z.number() })).default([]),
});
type Props = z.infer<typeof caseVideoSchema>;

type BgKind = "network" | "synth" | "stripes" | "blueprint" | "scan" | "paper" | "aurora";
type Palette = { bg1: string; bg2: string; text: string; dim: string; accent: string; card: string; line: string; bgKind: BgKind; blur: string; light: boolean; cap?: string; font: string; mono: string };

const SANS = '"Segoe UI", "Helvetica Neue", Arial, "Noto Sans", sans-serif';
const MONOSPACE = '"Cascadia Mono", Consolas, "SF Mono", "DejaVu Sans Mono", monospace';

// Every style is a whole look: colours, the kind of background, how cards are drawn, and the type (system fonts only: a web font load once stalled the CI renderer).
const PALETTES: Record<(typeof CASE_THEMES)[number], Palette> = {
  dark: { bg1: "#07101f", bg2: "#12294d", text: "#e8f1ff", dim: "#8fa0bd", accent: "#00e5a8", card: "rgba(16,30,54,0.82)", line: "rgba(0,229,168,0.32)", bgKind: "network", blur: "blur(16px)", light: false, font: SANS, mono: MONOSPACE },
  clean: { bg1: "#eef2fa", bg2: "#d5e0f5", text: "#101828", dim: "#5b6578", accent: "#2563eb", card: "rgba(255,255,255,0.88)", line: "rgba(37,99,235,0.25)", bgKind: "network", blur: "blur(12px)", light: true, font: SANS, mono: MONOSPACE },
  warm: { bg1: "#241711", bg2: "#46291a", text: "#fff3e6", dim: "#c3a58c", accent: "#ff8a3d", card: "rgba(60,38,26,0.8)", line: "rgba(255,138,61,0.28)", bgKind: "network", blur: "blur(16px)", light: false, font: SANS, mono: MONOSPACE },
  neon: { bg1: "#0a0118", bg2: "#2a0a52", text: "#fdf4ff", dim: "#c4a5e8", accent: "#ff3df2", card: "rgba(30,8,60,0.78)", line: "rgba(255,61,242,0.4)", bgKind: "synth", blur: "blur(14px)", light: false, font: SANS, mono: MONOSPACE },
  newsroom: { bg1: "#f6f4ef", bg2: "#e8e3d6", text: "#121212", dim: "#555555", accent: "#d7263d", card: "rgba(255,255,255,0.97)", line: "rgba(0,0,0,0.16)", bgKind: "stripes", blur: "none", light: true, cap: "#ff7a8a", font: '"Franklin Gothic Medium", "Arial Narrow", Arial, sans-serif', mono: MONOSPACE },
  blueprint: { bg1: "#0b2a4a", bg2: "#14487a", text: "#eaf6ff", dim: "#9cc4e8", accent: "#7dd3fc", card: "rgba(11,42,74,0.6)", line: "rgba(125,211,252,0.5)", bgKind: "blueprint", blur: "blur(6px)", light: false, font: MONOSPACE, mono: MONOSPACE },
  terminal: { bg1: "#020a04", bg2: "#07230f", text: "#c8ffd4", dim: "#5fae74", accent: "#33ff66", card: "rgba(3,20,8,0.82)", line: "rgba(51,255,102,0.38)", bgKind: "scan", blur: "blur(6px)", light: false, font: MONOSPACE, mono: MONOSPACE },
  editorial: { bg1: "#f3ede1", bg2: "#e4d9c3", text: "#1d1a16", dim: "#6b6254", accent: "#9a2f2f", card: "rgba(255,252,246,0.96)", line: "rgba(60,40,20,0.2)", bgKind: "paper", blur: "none", light: true, cap: "#ff9a9a", font: 'Georgia, Cambria, "Times New Roman", serif', mono: '"Courier New", Courier, monospace' },
  midnight: { bg1: "#0a0f24", bg2: "#18235a", text: "#eef1ff", dim: "#9aa6d6", accent: "#8ea2ff", card: "rgba(18,26,64,0.75)", line: "rgba(142,162,255,0.32)", bgKind: "aurora", blur: "blur(18px)", light: false, font: SANS, mono: MONOSPACE },
};
const FONT = "var(--font)";
const MONO = "var(--mono)";


const asset = (url: string) => (/^(https?:|data:)/.test(url) ? url : staticFile(url));

const useUnit = () => {
  const { width, height } = useVideoConfig();
  return { u: Math.min(width, height) / 1080, w: width, h: height, portrait: height > width };
};

const POINTS = 38;
const Network: React.FC<{ accent: string }> = ({ accent }) => {
  const frame = useCurrentFrame();
  const { u, w, h } = useUnit();
  const pts = Array.from({ length: POINTS }, (_, i) => {
    const x0 = random(`x${i}`) * w, y0 = random(`y${i}`) * h, ph = random(`p${i}`) * 6.28, sp = 0.006 + random(`s${i}`) * 0.01;
    return { x: x0 + Math.sin(frame * sp + ph) * 60 * u, y: y0 + Math.cos(frame * sp * 1.3 + ph) * 50 * u, r: (3 + random(`r${i}`) * 4) * u };
  });
  const links: React.ReactNode[] = [];
  const reach = 300 * u;
  for (let i = 0; i < POINTS; i++) for (let j = i + 1; j < POINTS; j++) {
    const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
    if (d < reach) links.push(<line key={`${i}-${j}`} x1={pts[i].x} y1={pts[i].y} x2={pts[j].x} y2={pts[j].y} stroke={accent} strokeOpacity={(1 - d / reach) * 0.5} strokeWidth={1.8 * u} />);
  }
  return (
    <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>
      {links}
      {pts.map((q, i) => <circle key={i} cx={q.x} cy={q.y} r={q.r} fill={accent} fillOpacity={0.75} />)}
    </svg>
  );
};

const Backdrop: React.FC<{ p: Palette; accent: string }> = ({ p, accent }) => {
  const frame = useCurrentFrame();
  const { u, w, h } = useUnit();
  const slow = (frame * 0.4) % (80 * u);
  const base = `radial-gradient(ellipse at 30% 20%, ${p.bg2}, ${p.bg1} 70%)`;
  const glowBlobs = `radial-gradient(circle at ${50 + 30 * Math.sin(frame / 90)}% ${45 + 25 * Math.cos(frame / 120)}%, ${accent}30, transparent 45%), radial-gradient(circle at ${75 - 25 * Math.cos(frame / 100)}% ${70 - 20 * Math.sin(frame / 80)}%, #3b82f630, transparent 40%)`;
  const fade = "radial-gradient(ellipse at center, black 30%, transparent 85%)";
  if (p.bgKind === "synth") {
    const sunY = h * 0.52;
    return (
      <AbsoluteFill style={{ background: `linear-gradient(180deg, ${p.bg1} 0%, ${p.bg2} 55%, ${p.bg1} 100%)` }}>
        <div style={{ position: "absolute", left: "50%", top: sunY - 220 * u, width: 440 * u, height: 440 * u, marginLeft: -220 * u, borderRadius: "50%", background: `linear-gradient(180deg, #ffd23f 0%, ${accent} 60%, #7a1fff 100%)`, opacity: 0.55, boxShadow: `0 0 ${120 * u}px ${accent}88` }} />
        <div style={{ position: "absolute", left: "-30%", right: "-30%", top: sunY, bottom: 0, perspective: 700 * u }}>
          <div style={{ width: "100%", height: "180%", transformOrigin: "50% 0%", transform: "rotateX(62deg)", backgroundImage: `linear-gradient(${accent} 2px, transparent 2px), linear-gradient(90deg, ${accent} 2px, transparent 2px)`, backgroundSize: `${90 * u}px ${90 * u}px`, backgroundPosition: `0 ${(frame * 1.5) % (90 * u)}px`, opacity: 0.45, maskImage: "linear-gradient(180deg, transparent, black 30%)", WebkitMaskImage: "linear-gradient(180deg, transparent, black 30%)" }} />
        </div>
      </AbsoluteFill>
    );
  }
  if (p.bgKind === "stripes") {
    return (
      <AbsoluteFill style={{ background: base }}>
        <AbsoluteFill style={{ backgroundImage: `repeating-linear-gradient(135deg, ${p.line} 0px, ${p.line} 2px, transparent 2px, transparent ${46 * u}px)`, backgroundPosition: `${slow}px 0`, opacity: 0.55 }} />
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 26 * u, background: accent }} />
        <div style={{ position: "absolute", right: -160 * u, top: -160 * u, width: 520 * u, height: 520 * u, borderRadius: "50%", background: accent, opacity: 0.1 }} />
      </AbsoluteFill>
    );
  }
  if (p.bgKind === "blueprint") {
    return (
      <AbsoluteFill style={{ background: base }}>
        <AbsoluteFill style={{ backgroundImage: `linear-gradient(${p.line} 1px, transparent 1px), linear-gradient(90deg, ${p.line} 1px, transparent 1px)`, backgroundSize: `${28 * u}px ${28 * u}px`, backgroundPosition: `${slow / 3}px ${slow / 3}px`, opacity: 0.28 }} />
        <AbsoluteFill style={{ backgroundImage: `linear-gradient(${p.line} 2px, transparent 2px), linear-gradient(90deg, ${p.line} 2px, transparent 2px)`, backgroundSize: `${140 * u}px ${140 * u}px`, backgroundPosition: `${slow / 3}px ${slow / 3}px`, opacity: 0.5 }} />
        <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>
          {[[60, 60], [w - 60, 60], [60, h - 60], [w - 60, h - 60]].map(([x, y], i) => <path key={i} d={`M${x - 26 * u} ${y}H${x + 26 * u}M${x} ${y - 26 * u}V${y + 26 * u}`} stroke={accent} strokeWidth={2.5 * u} fill="none" />)}
          <circle cx={w * 0.82} cy={h * 0.3} r={150 * u} stroke={p.line} strokeWidth={2 * u} fill="none" strokeDasharray={`${10 * u} ${14 * u}`} />
        </svg>
      </AbsoluteFill>
    );
  }
  if (p.bgKind === "scan") {
    const sweep = ((frame * 4) % (h + 300 * u)) - 150 * u;
    return (
      <AbsoluteFill style={{ background: base }}>
        <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(0,0,0,0.38) 0px, rgba(0,0,0,0.38) 2px, transparent 3px, transparent 5px)" }} />
        <div style={{ position: "absolute", left: 0, right: 0, top: sweep, height: 150 * u, background: `linear-gradient(180deg, transparent, ${accent}22, transparent)` }} />
        <AbsoluteFill style={{ backgroundImage: `linear-gradient(${p.line} 1px, transparent 1px), linear-gradient(90deg, ${p.line} 1px, transparent 1px)`, backgroundSize: `${60 * u}px ${60 * u}px`, opacity: 0.22, maskImage: fade, WebkitMaskImage: fade }} />
      </AbsoluteFill>
    );
  }
  if (p.bgKind === "paper") {
    return (
      <AbsoluteFill style={{ background: base }}>
        <AbsoluteFill style={{ backgroundImage: `repeating-linear-gradient(0deg, transparent 0px, transparent ${54 * u}px, ${p.line} ${54 * u}px, ${p.line} ${55 * u}px)`, opacity: 0.55 }} />
        <AbsoluteFill style={{ background: `radial-gradient(ellipse at center, transparent 55%, ${p.bg2} 130%)` }} />
        <div style={{ position: "absolute", left: 70 * u, top: 0, bottom: 0, width: 2 * u, background: accent, opacity: 0.35 }} />
      </AbsoluteFill>
    );
  }
  if (p.bgKind === "aurora") {
    const blob = (cx: number, cy: number, size: number, color: string, ph: number) => (
      <div style={{ position: "absolute", left: `${cx + 14 * Math.sin(frame / 110 + ph)}%`, top: `${cy + 12 * Math.cos(frame / 140 + ph)}%`, width: size * u, height: size * u, marginLeft: -size * u / 2, marginTop: -size * u / 2, borderRadius: "50%", background: color, filter: `blur(${110 * u}px)`, opacity: 0.55 }} />
    );
    return (
      <AbsoluteFill style={{ background: `linear-gradient(160deg, ${p.bg1}, ${p.bg2})` }}>
        {blob(25, 30, 900, accent, 0)}
        {blob(75, 65, 800, "#7a5cff", 2)}
        {blob(55, 90, 700, "#19c6ff", 4)}
        <AbsoluteFill style={{ backgroundImage: `radial-gradient(${p.line} 1.5px, transparent 1.5px)`, backgroundSize: `${46 * u}px ${46 * u}px`, opacity: 0.35 }} />
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ background: base }}>
      <AbsoluteFill style={{ background: glowBlobs }} />
      <AbsoluteFill style={{ backgroundImage: `linear-gradient(${p.line} 1px, transparent 1px), linear-gradient(90deg, ${p.line} 1px, transparent 1px)`, backgroundSize: `${80 * u}px ${80 * u}px`, backgroundPosition: `${slow}px ${slow}px`, opacity: p.light ? 0.5 : 0.6, maskImage: fade, WebkitMaskImage: fade }} />
      <Network accent={accent} />
      {!p.light && <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(255,255,255,0.025) 0px, rgba(255,255,255,0.025) 1px, transparent 2px, transparent 4px)" }} />}
    </AbsoluteFill>
  );
};

const enter = (frame: number, delay: number, fps: number) =>
  spring({ frame: frame - delay, fps, config: { damping: 18, stiffness: 120 } });

type Pal = Palette;
type SceneProps = { labels: string[]; cues: number[]; p: Pal; accent: string; frames: number };

// the frame at which each label is spoken: the cue from the narration, else evenly across the first 70% of the section
const cueFrames = (n: number, cues: number[], frames: number, fps: number) =>
  Array.from({ length: n }, (_, i) => (cues[i] !== undefined ? Math.round(cues[i] * fps) : Math.round((i / Math.max(1, n)) * frames * 0.7) + 6));
// the label being spoken now: the last one whose cue has passed
const activeIndex = (frame: number, at: number[]) => at.reduce((a, f, i) => (frame >= f ? i : a), -1);

// Simple line icons (24 x 24), picked by the words of a label, so diagram boxes and cards carry a picture instead of only text.
type IconName = "server" | "laptop" | "lock" | "globe" | "warning" | "shield" | "file" | "money" | "clock" | "ship" | "plane" | "user" | "terminal" | "key" | "dot";
const ICON_RULES: [RegExp, IconName][] = [
  [/server|data ?cent|cloud|database/i, "server"],
  [/ransom|encrypt|password|lock|credential|hostage/i, "lock"],
  [/\bkey\b|token|certificate/i, "key"],
  [/country|countries|world|global|internet|network|international|nation/i, "globe"],
  [/flight|plane|airline|airport|\bair\b/i, "plane"],
  [/ship|vessel|tug|canal|boat|cargo|container|port\b|sea\b/i, "ship"],
  [/money|\$|cost|loss|fine|compensation|bitcoin|payment|billion|million|dollar|revenue|damage/i, "money"],
  [/patch|protect|defen|prevent|backup|secure|security|update|test|monitor|policy|train/i, "shield"],
  [/command|terminal|script|code|shell|exploit|execute|payload|backdoor|port \d|smb/i, "terminal"],
  [/user|people|customer|staff|crew|employee|worker|hospital|patient|attacker|hacker|group/i, "user"],
  [/file|record|document|data|log\b|backup/i, "file"],
  [/computer|laptop|pc\b|machine|device|system|windows|endpoint|client|sensor|host/i, "laptop"],
  [/attack|breach|fail|crash|error|block|outage|warning|infect|malware|virus|worm|spread|vulnerab|aground|stuck|fault/i, "warning"],
  [/\b(19|20)\d\d\b|january|february|march|april|may\b|june|july|august|september|october|november|december|day|hour|week|month|year|time|timeline/i, "clock"],
];
const iconFor = (label: string): IconName => (ICON_RULES.find(([re]) => re.test(label)) || [null, "dot"])[1] as IconName;

const Icon: React.FC<{ name: IconName; size: number; color: string }> = ({ name, size, color }) => {
  const common = { fill: "none", stroke: color, strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const shapes: Record<IconName, React.ReactNode> = {
    server: <><rect x="3" y="3" width="18" height="7" rx="2" /><rect x="3" y="14" width="18" height="7" rx="2" /><path d="M7 6.5h.01M7 17.5h.01" /></>,
    laptop: <><rect x="4" y="5" width="16" height="11" rx="1.5" /><path d="M2 19h20" /></>,
    lock: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>,
    key: <><circle cx="8" cy="15" r="4" /><path d="M11 12l9-9M17 6l3 3" /></>,
    globe: <><circle cx="12" cy="12" r="10" /><ellipse cx="12" cy="12" rx="4" ry="10" /><path d="M2 12h20" /></>,
    plane: <path d="M2 13l20-9-7 17-3-7z" />,
    ship: <><path d="M3 16l2 5h14l2-5z" /><rect x="7" y="9" width="10" height="7" /><path d="M12 3v6" /></>,
    money: <><circle cx="12" cy="12" r="10" /><path d="M12 6v12M9 9.5c0-2.2 6-2.2 6 0s-6 2.2-6 4.5 6 2.2 6 0" /></>,
    shield: <path d="M12 2l8 3v7c0 5-4 8-8 10-4-2-8-5-8-10V5z" />,
    terminal: <><path d="M4 17l6-6-6-6" /><path d="M12 19h8" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></>,
    file: <><path d="M6 2h8l4 4v16H6z" /><path d="M14 2v4h4" /></>,
    clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
    warning: <><path d="M12 3L22 20H2z" /><path d="M12 9v5M12 17h.01" /></>,
    dot: <circle cx="12" cy="12" r="4" />,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0 }} {...common}>{shapes[name]}</svg>;
};

const glow = (on: boolean, accent: string, u: number) => (on ? `0 0 ${34 * u}px ${accent}88` : "none");

const Timeline: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const { u, portrait } = useUnit();
  const at = cueFrames(labels.length, cues, frames, fps);
  const act = activeIndex(frame, at);
  const aw = width - 140 * u, ah = portrait ? height * 0.6 : height * 0.5;
  const pos = (i: number) => (portrait ? { x: 90 * u, y: (ah * (i + 0.5)) / labels.length } : { x: (aw * (i + 0.5)) / labels.length, y: ah / 2 });
  // the line is drawn up to the node being spoken, and keeps travelling toward the next one
  const lineEnd = act < 0 ? 0 : act + (act + 1 < labels.length ? interpolate(frame, [at[act], Math.max(at[act] + 1, at[act + 1])], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0);
  const first = pos(0), last = pos(labels.length - 1);
  const share = lineEnd / Math.max(1, labels.length - 1);
  const head = { x: first.x + (last.x - first.x) * share, y: first.y + (last.y - first.y) * share };
  return (
    <div style={{ position: "relative", width: aw, height: ah }}>
      <svg width={aw} height={ah} style={{ position: "absolute", inset: 0 }}>
        <line x1={first.x} y1={first.y} x2={last.x} y2={last.y} stroke={p.line} strokeWidth={6 * u} strokeLinecap="round" />
        <line x1={first.x} y1={first.y} x2={head.x} y2={head.y} stroke={accent} strokeWidth={6 * u} strokeLinecap="round" />
        {act >= 0 && <circle cx={head.x} cy={head.y} r={14 * u} fill={accent} style={{ filter: `drop-shadow(0 0 ${14 * u}px ${accent})` }} />}
      </svg>
      {labels.map((l, i) => {
        const t = enter(frame, at[i], fps);
        const { x, y } = pos(i);
        const above = !portrait && i % 2 === 0;
        const on = i === act;
        return (
          <React.Fragment key={i}>
            <div style={{ position: "absolute", left: x - 38 * u, top: y - 38 * u, width: 76 * u, height: 76 * u, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: i <= act ? `${accent}33` : p.bg1, border: `${4 * u}px solid ${accent}`, transform: `scale(${0.4 + 0.6 * t})`, boxShadow: glow(on, accent, u) }}><Icon name={iconFor(labels[i])} size={40 * u} color={accent} /></div>
            <div style={{ position: "absolute", left: portrait ? x + 70 * u : x - 230 * u, ...(portrait ? { top: y - 34 * u } : above ? { bottom: ah - y + 64 * u } : { top: y + 64 * u }), width: portrait ? aw - x - 70 * u : 460 * u, textAlign: portrait ? "left" : "center", fontFamily: FONT, fontSize: 44 * u, fontWeight: 700, lineHeight: 1.15, color: i <= act ? p.text : p.dim, opacity: t, transformOrigin: portrait ? "left center" : "center", transform: `translateY(${(1 - t) * (above ? 30 : -30) * u}px) scale(${on ? 1.06 : 1})` }}>{l}</div>
          </React.Fragment>
        );
      })}
    </div>
  );
};

const Flow: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const { u, portrait } = useUnit();
  const n = labels.length;
  const at = cueFrames(n, cues, frames, fps);
  const act = activeIndex(frame, at);
  const aw = width - 140 * u, ah = portrait ? height * 0.62 : height * 0.5;
  const nw = portrait ? Math.min(820 * u, aw) : Math.min(400 * u, aw / n - 70 * u), nh = portrait ? Math.min(140 * u, ah / n - 50 * u) : 190 * u;
  const c = (i: number) => (portrait ? { x: aw / 2, y: (ah * (i + 0.5)) / n } : { x: (aw * (i + 0.5)) / n, y: ah / 2 });
  return (
    <div style={{ position: "relative", width: aw, height: ah }}>
      <svg width={aw} height={ah} style={{ position: "absolute", inset: 0 }}>
        {labels.slice(0, -1).map((_, i) => {
          const a = c(i), b = c(i + 1);
          const from = portrait ? { x: a.x, y: a.y + nh / 2 } : { x: a.x + nw / 2, y: a.y };
          const to = portrait ? { x: b.x, y: b.y - nh / 2 } : { x: b.x - nw / 2, y: b.y };
          const prog = interpolate(frame, [at[i], Math.max(at[i] + 1, at[i + 1])], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const px = from.x + (to.x - from.x) * prog, py = from.y + (to.y - from.y) * prog;
          return (
            <g key={i}>
              <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={p.line} strokeWidth={4 * u} strokeDasharray={`${12 * u} ${10 * u}`} />
              <line x1={from.x} y1={from.y} x2={px} y2={py} stroke={accent} strokeWidth={5 * u} />
              {prog > 0 && prog < 1 && <circle cx={px} cy={py} r={11 * u} fill={accent} style={{ filter: `drop-shadow(0 0 ${14 * u}px ${accent})` }} />}
            </g>
          );
        })}
      </svg>
      {labels.map((l, i) => {
        const t = enter(frame, at[i], fps);
        const { x, y } = c(i);
        const on = i === act;
        return (
          <div key={i} style={{ position: "absolute", left: x - nw / 2, top: y - nh / 2, width: nw, height: nh, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", boxSizing: "border-box", padding: 14 * u, background: p.card, backdropFilter: p.blur, border: `${on ? 4 : 2}px solid ${i <= act ? accent : p.line}`, borderRadius: 22 * u, fontFamily: FONT, fontSize: 38 * u, fontWeight: 700, color: p.text, opacity: t, transform: `scale(${(0.85 + 0.15 * t) * (on ? 1.05 : 1)})`, boxShadow: glow(on, accent, u), flexDirection: "column", gap: 10 * u }}>
            <Icon name={iconFor(l)} size={54 * u} color={accent} />
            <span>{l}</span>
          </div>
        );
      })}
    </div>
  );
};

// "5,078 flights cancelled" -> count the number up, show the words under it
const splitNumber = (label: string) => {
  // "5 to 7 minutes" / "5-7 minutes": the range stays together (the first number counts up, the end is shown as is)
  const range = label.match(/(\d[\d,.]*)\s*(?:to|-|–)\s*(\d[\d,.]*)(?=\s|$)/);
  // a unit written right after the number stays with it: 130C, 130 °C, 20 g, 500 ml, 3 cm
  const m = (range ? label.match(/(\d[\d,.]*)/) : null) || label.match(/(\$?\s?\d[\d,.]*\+?\s?(?:%|[kKmMbB]\b|[Mm]illion|[Bb]illion|[Tt]rillion|\s?°\s?[CF]\b|[CF](?=\s)|(?:kg|g|ml|cm|mm|km)(?=\s|$))?)/);
  if (!m) return null;
  const raw = m[1].trim();
  const num = parseFloat(raw.replace(/[^\d.]/g, "").replace(/\.(?=.*\.)/g, ""));
  if (!isFinite(num)) return null;
  if (range && range.index !== undefined) {
    const rest = (label.slice(0, range.index) + " " + label.slice(range.index + range[0].length)).replace(/\s+/g, " ").trim();
    return { raw: range[1], num: parseFloat(range[1].replace(/[^\d.]/g, "")), rest, prefix: "", suffix: "", rangeEnd: range[2] };
  }
  const rest = (label.slice(0, m.index) + " " + label.slice((m.index || 0) + m[1].length)).replace(/\s+/g, " ").trim();
  return { raw, num, rest, prefix: raw.startsWith("$") ? "$" : "", suffix: raw.replace(/^\$?\s?[\d,.]+/, "").trim().replace(/^°?\s?([CF])$/, "°$1"), rangeEnd: "" };
};

const Counters: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
  const dense = labels.length > 3 && !portrait;      // four cards in two landscape rows: smaller, so they clear the caption bar
  const at = cueFrames(labels.length, cues, frames, fps);
  const act = activeIndex(frame, at);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 24 * u, justifyContent: "center", alignContent: "center", width: "100%" }}>
      {labels.map((l, i) => {
        const delay = at[i];
        const t = enter(frame, delay, fps);
        const parts = splitNumber(l);
        const progress = interpolate(frame - delay, [0, 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const decimals = parts && /\.\d/.test(parts.raw) ? (parts.raw.split(".")[1].match(/^\d+/) || [""])[0].length : 0;
        const shown = parts ? (parts.num * progress).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : null;
        const on = i === act;
        return (
          <div key={i} style={{ background: p.card, backdropFilter: p.blur, border: `1px solid ${p.line}`, borderTop: `5px solid ${accent}`, borderRadius: 22 * u, padding: `${(dense ? 14 : 26) * u}px ${(dense ? 26 : 34) * u}px`, minWidth: (portrait ? 800 : dense ? 400 : 480) * u, textAlign: "center", display: "flex", flexDirection: "column", justifyContent: "center", opacity: t, transform: `translateY(${(1 - t) * 50 * u}px) scale(${on ? 1.05 : 1})`, boxShadow: glow(on, accent, u) }}>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: (dense ? 4 : 10) * u }}><Icon name={iconFor(l)} size={(dense ? 40 : 56) * u} color={accent} /></div>
            {parts ? (
              <>
                <div style={{ fontFamily: FONT, fontSize: (dense ? 72 : 96) * u, fontWeight: 800, color: accent, lineHeight: 1 }}>{parts.prefix}{shown}{parts.rangeEnd ? `–${parts.rangeEnd}` : ""}{parts.suffix ? (/^[+%°]/.test(parts.suffix) ? parts.suffix : ` ${parts.suffix}`) : ""}</div>
                <div style={{ fontFamily: FONT, fontSize: (dense ? 34 : 42) * u, color: p.text, marginTop: (dense ? 8 : 14) * u }}>{parts.rest}</div>
              </>
            ) : (
              <div style={{ fontFamily: FONT, fontSize: 56 * u, fontWeight: 700, color: p.text }}>{l}</div>
            )}
          </div>
        );
      })}
    </div>
  );
};

const Checklist: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  const at = cueFrames(labels.length, cues, frames, fps);
  const act = activeIndex(frame, at);
  const longest = Math.max(0, ...labels.map((l) => l.length));
  const fs = longest > 55 ? 36 : longest > 38 ? 42 : 48;       // long lines wrap to two rows: smaller type keeps the rows clear of the heading and the caption
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: (longest > 38 ? 18 : 28) * u, width: "100%", maxWidth: 1400 * u }}>
      {labels.map((l, i) => {
        const delay = at[i];
        const t = enter(frame, delay, fps);
        const tick = interpolate(frame - delay - 8, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const on = i === act;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 30 * u, background: p.card, backdropFilter: p.blur, border: `${on ? 3 : 1}px solid ${on ? accent : p.line}`, borderRadius: 20 * u, padding: `${26 * u}px ${32 * u}px`, opacity: t, transform: `translateX(${(1 - t) * -80 * u}px) scale(${on ? 1.03 : 1})`, transformOrigin: "left center", boxShadow: glow(on, accent, u) }}>
            <div style={{ width: 58 * u, height: 58 * u, borderRadius: 14 * u, border: `3px solid ${accent}`, background: tick > 0.5 ? `${accent}33` : "transparent", display: "flex", alignItems: "center", justifyContent: "center", color: accent, fontSize: 44 * u, fontFamily: FONT, fontWeight: 800, flexShrink: 0 }}>
              <span style={{ opacity: tick, transform: `scale(${0.4 + 0.6 * tick})` }}>✓</span>
            </div>
            <div style={{ fontFamily: FONT, fontSize: fs * u, fontWeight: 600, color: p.text }}>{l}</div>
          </div>
        );
      })}
    </div>
  );
};

const Terminal: React.FC<SceneProps> = ({ labels, cues, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  const at = cueFrames(labels.length, cues, frames, fps);
  return (
    <div style={{ background: "rgba(2,6,12,0.92)", border: `1px solid ${accent}55`, borderRadius: 18 * u, padding: 40 * u, width: "100%", maxWidth: 1400 * u, fontFamily: MONO, boxShadow: `0 0 ${40 * u}px ${accent}22` }}>
      {labels.map((l, i) => {
        const chars = Math.max(0, Math.min(l.length, Math.floor((frame - at[i]) * 1.6)));
        return (
          <div key={i} style={{ fontSize: 44 * u, color: "#9fffd9", marginBottom: 20 * u, minHeight: 54 * u }}>
            <span style={{ color: accent }}>$ </span>{l.slice(0, chars)}{chars < l.length && chars > 0 ? <span style={{ opacity: frame % 20 < 10 ? 1 : 0 }}>▌</span> : null}
          </div>
        );
      })}
    </div>
  );
};

const Quote: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  const at = cueFrames(labels.length, cues, frames, fps);
  return (
    <div style={{ borderLeft: `${10 * u}px solid ${accent}`, paddingLeft: 44 * u, maxWidth: 1400 * u }}>
      {labels.map((l, i) => {
        const t = enter(frame, Math.max(4, at[i]), fps);
        return <div key={i} style={{ fontFamily: FONT, fontSize: (i === 0 ? 78 : 48) * u, fontWeight: i === 0 ? 800 : 500, color: i === 0 ? p.text : p.dim, lineHeight: 1.2, marginBottom: 18 * u, opacity: t, transform: `translateY(${(1 - t) * 30 * u}px)` }}>{l}</div>;
      })}
    </div>
  );
};

// real typeset formulas: KaTeX writes MathML (no web fonts to load, so a render never waits for one); a label that is not
// formula-like is shown as plain text
const looksLikeTex = (s: string) => /[\\^_=]/.test(s);
const Equation: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  const at = cueFrames(labels.length, cues, frames, fps);
  const act = activeIndex(frame, at);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 34 * u, alignItems: "center", width: "100%" }}>
      {labels.map((l, i) => {
        const t = enter(frame, at[i], fps);
        const on = i === act;
        const html = looksLikeTex(l) ? katex.renderToString(l, { output: "mathml", throwOnError: false, displayMode: true }) : null;
        return (
          <div key={i} style={{ background: p.card, backdropFilter: p.blur, border: `${on ? 3 : 1}px solid ${on ? accent : p.line}`, borderRadius: 22 * u, padding: `${22 * u}px ${48 * u}px`, opacity: t, transform: `scale(${(0.9 + 0.1 * t) * (on ? 1.04 : 1)})`, boxShadow: glow(on, accent, u), color: p.text, fontFamily: FONT, fontSize: 78 * u, fontWeight: 600 }}>
            {html ? <span dangerouslySetInnerHTML={{ __html: html }} /> : l}
          </div>
        );
      })}
    </div>
  );
};

// compare: two columns side by side. Each label is "left | right"; the first label holds the two headings. A label without "|" is shown in the left column.
const Compare: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
  const at = cueFrames(labels.length, cues, frames, fps);
  const act = activeIndex(frame, at);
  const rows = labels.map((l) => {
    const [a, ...rest] = l.split("|");
    return [a.trim(), rest.join("|").trim()];
  });
  const side = (text: string, i: number, right: boolean, head: boolean) => {
    const t = enter(frame, at[i] + (right ? 4 : 0), fps);
    const color = right ? accent : p.dim;
    return (
      <div style={{ flex: 1, background: p.card, backdropFilter: p.blur, border: `${head ? 3 : 1}px solid ${head ? color : p.line}`, borderTop: head ? `6px solid ${color}` : undefined,
        borderRadius: 20 * u, padding: `${(head ? 24 : 20) * u}px ${28 * u}px`, fontFamily: FONT, fontSize: (head ? 54 : portrait ? 36 : 40) * u, fontWeight: head ? 800 : 600, color: head ? p.text : p.text,
        textAlign: "center", opacity: t, transform: `translateX(${(1 - t) * (right ? 60 : -60) * u}px) scale(${i === act && !head ? 1.03 : 1})`, boxShadow: glow(i === act && !head, accent, u),
        display: "flex", alignItems: "center", justifyContent: "center", minHeight: (head ? 100 : 92) * u }}>
        {text}
      </div>
    );
  };
  const vs = enter(frame, at[0], fps);
  return (
    <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 20 * u, width: "100%", maxWidth: 1500 * u }}>
      {rows.map(([a, b], i) => (
        <div key={i} style={{ display: "flex", gap: (i === 0 ? 76 : 76) * u }}>
          {side(a, i, false, i === 0 && rows.length > 1)}
          {side(b, i, true, i === 0 && rows.length > 1)}
        </div>
      ))}
      <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 2 * u, marginLeft: -u, background: p.line, opacity: vs }} />
      <div style={{ position: "absolute", left: "50%", top: 20 * u, marginLeft: -34 * u, width: 68 * u, height: 68 * u, borderRadius: "50%", background: accent, color: p.bg1, display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: FONT, fontWeight: 900, fontSize: 28 * u, transform: `scale(${vs})`, boxShadow: `0 0 ${30 * u}px ${accent}88` }}>VS</div>
    </div>
  );
};

// chart: horizontal bars drawn to scale. Each label is "Name: number" (a unit may follow); the bars grow and the numbers count up as each is spoken.
const Chart: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
  const at = cueFrames(labels.length, cues, frames, fps);
  const act = activeIndex(frame, at);
  const items = labels.map((l) => {
    const colon = l.indexOf(":");
    const name = colon > 0 ? l.slice(0, colon).trim() : "";
    const parts = splitNumber(colon > 0 ? l.slice(colon + 1) : l);
    return { name: name || (parts ? parts.rest : l), parts, raw: l };
  });
  const max = Math.max(1, ...items.map((it) => (it.parts ? it.parts.num : 0)));
  const track = (portrait ? 560 : 820) * u;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 26 * u, width: "100%", maxWidth: 1500 * u }}>
      {items.map((it, i) => {
        const t = enter(frame, at[i], fps);
        const grow = interpolate(frame - at[i], [0, 36], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const value = it.parts ? it.parts.num : 0;
        const decimals = it.parts && /\.\d/.test(it.parts.raw) ? (it.parts.raw.split(".")[1].match(/^\d+/) || [""])[0].length : 0;
        const shown = it.parts ? (value * grow).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : "";
        const on = i === act;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 28 * u, opacity: t, transform: `translateX(${(1 - t) * -50 * u}px)` }}>
            <div style={{ width: (portrait ? 240 : 330) * u, fontFamily: FONT, fontSize: (portrait ? 32 : 38) * u, fontWeight: 600, color: on ? p.text : p.dim, textAlign: "right", lineHeight: 1.15 }}>{it.name}</div>
            <div style={{ position: "relative", width: track, height: 62 * u, borderRadius: 14 * u, background: p.card, backdropFilter: p.blur, border: `1px solid ${p.line}`, overflow: "hidden", boxShadow: glow(on, accent, u) }}>
              <div style={{ width: `${(it.parts ? (value / max) * 100 : 0) * grow}%`, height: "100%", background: `linear-gradient(90deg, ${accent}aa, ${accent})`, borderRadius: 14 * u }} />
            </div>
            <div style={{ minWidth: 190 * u, fontFamily: FONT, fontSize: (portrait ? 40 : 48) * u, fontWeight: 800, color: accent }}>
              {it.parts ? `${it.parts.prefix}${shown}${it.parts.suffix ? (/^[+%]/.test(it.parts.suffix) ? it.parts.suffix : ` ${it.parts.suffix}`) : ""}` : ""}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// A Mermaid diagram of any type, laid out by Mermaid's own engine (so nothing overlaps whatever the model wrote). It is drawn inside the same glass
// panel as the other scenes, across the whole width, with large type (the panel is wide enough that a diagram of up to six nodes is not scaled down),
// coloured like the chosen look, and revealed step by step: nodes in order of the drawing, each arrow with the node it points to. The step being
// spoken glows, the earlier ones settle back. A diagram type without nodes is simply shown whole. If Mermaid cannot draw it, `fallback` is shown.
const MAX_GROW = 1.7;
const CAMERA_WINDOW = 4;      // a chain longer than this is shown this many steps at a time, the view following the story
const MermaidDiagram: React.FC<{ code: string; p: Pal; accent: string; frames: number; fallback: React.ReactNode }> = ({ code, p, accent, frames, fallback }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
  const host = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState("");
  const [failed, setFailed] = useState(false);
  const [handle] = useState(() => delayRender("Drawing the diagram"));
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base", fontFamily: p.font,
          // the type is as big as the whole drawing can be scaled: a tall frame wants wide boxes with one line of text (a short chain), a wide frame narrow boxes with wrapped text (a short row)
          flowchart: { useMaxWidth: false, htmlLabels: true, curve: "basis", padding: 24, nodeSpacing: portrait ? 60 : 52, rankSpacing: portrait ? 64 : 54, wrappingWidth: portrait ? 560 : 170 },
          sequence: { useMaxWidth: false, mirrorActors: false, actorMargin: 100, messageMargin: 26, width: 300, height: 54, boxMargin: 8, noteMargin: 12, actorFontSize: 40, messageFontSize: 40, noteFontSize: 40 },
          fontSize: 30,
          themeVariables: { fontFamily: p.font, fontSize: "30px" } });
        const out = await mermaid.render("sf-mmd-" + Math.random().toString(36).slice(2, 9), code);
        if (alive) setSvg(out.svg);
      } catch (e) {
        console.warn("[layout] the diagram could not be drawn: " + String(e).slice(0, 240));
        if (alive) { setSvg(""); setFailed(true); }
      } finally {
        continueRender(handle);
      }
    })();
    return () => { alive = false; };
  }, [code]);
  useLayoutEffect(() => {
    const box = host.current;
    const el = box?.querySelector("svg") as SVGSVGElement | null;
    if (!box || !el) return;
    // the drawing's own view box, remembered on the first pass (the camera changes it afterwards)
    if (!el.dataset.nat) {
      const vb = el.viewBox.baseVal;
      const r = el.getBoundingClientRect();
      el.dataset.nat = `${vb ? vb.x : 0} ${vb ? vb.y : 0} ${vb && vb.width ? vb.width : r.width || 1} ${vb && vb.height ? vb.height : r.height || 1}`;
    }
    const [nx, ny, nw, nh] = el.dataset.nat.split(" ").map(Number);
    el.style.maxWidth = "none";
    const isSequence = !!el.querySelector("rect.actor-top");
    const nodes = Array.from(el.querySelectorAll<SVGGElement>("g.node, g.mindmap-node, g.statediagram-state"));
    const start = 0.8 * fps, end = Math.max(start + fps, frames - 2.5 * fps);
    const at = (i: number) => start + ((end - start) * i) / Math.max(1, nodes.length - 1);
    const shown = (i: number) => interpolate(frame, [at(i), at(i) + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    let current = -1;
    nodes.forEach((_, i) => { if (shown(i) > 0.5) current = i; });

    // The camera: a chain of more than CAMERA_WINDOW nodes is shown a few steps at a time, the view following the story (the step being told and the
    // ones before it) and gliding as each new step appears, so the type stays large however long the chain is. Everything else is shown whole.
    const camera = nodes.length > CAMERA_WINDOW && !!el.querySelector("g.node");
    if (camera) {
      const boxes = nodes.map((n) => {
        const bb = n.getBBox();
        const m = n.transform.baseVal.numberOfItems ? n.transform.baseVal.consolidate()?.matrix : null;
        return { x0: bb.x + (m ? m.e : 0), y0: bb.y + (m ? m.f : 0), x1: bb.x + bb.width + (m ? m.e : 0), y1: bb.y + bb.height + (m ? m.f : 0) };
      });
      const win = (c: number) => {
        const idx = boxes.map((_, i) => i).filter((i) => i <= c && i > c - CAMERA_WINDOW);
        return { x0: Math.min(...idx.map((i) => boxes[i].x0)), y0: Math.min(...idx.map((i) => boxes[i].y0)), x1: Math.max(...idx.map((i) => boxes[i].x1)), y1: Math.max(...idx.map((i) => boxes[i].y1)) };
      };
      const c = Math.max(0, current);
      const from = win(Math.max(0, c - 1)), to = win(c);
      const t = c === 0 ? 1 : shown(c);
      const lerp = (x: number, y: number) => x + (y - x) * t;
      const x0 = lerp(from.x0, to.x0), x1 = lerp(from.x1, to.x1), y0 = lerp(from.y0, to.y0), y1 = lerp(from.y1, to.y1);
      const pad = 36;
      let w = x1 - x0 + 2 * pad, h = y1 - y0 + 2 * pad;
      const aspect = box.clientWidth / Math.max(1, box.clientHeight);
      if (w / h < aspect) w = h * aspect; else h = w / aspect;
      const minW = box.clientWidth / MAX_GROW;                          // never zoom in so far that a single node becomes a giant
      if (w < minW) { const f = minW / w; w *= f; h *= f; }
      el.setAttribute("viewBox", `${(x0 + x1) / 2 - w / 2} ${(y0 + y1) / 2 - h / 2} ${w} ${h}`);
      el.setAttribute("preserveAspectRatio", "xMidYMid meet");
      el.style.width = `${box.clientWidth}px`;
      el.style.height = `${box.clientHeight}px`;
    } else {
      el.setAttribute("viewBox", `${nx} ${ny} ${nw} ${nh}`);
      const k = Math.min(box.clientWidth / nw, box.clientHeight / nh, isSequence ? 3 : MAX_GROW);
      el.style.width = `${nw * k}px`;
      el.style.height = `${nh * k}px`;
    }

    // a sequence diagram: the participants stay on screen, the messages appear one at a time (each is its text followed by its line), the one being told brightest
    if (isSequence) {
      const parts = Array.from(el.querySelectorAll<SVGElement>("text.messageText, line.messageLine0, line.messageLine1, path.messageLine0, path.messageLine1"));
      const steps: SVGElement[][] = [];
      parts.forEach((q) => { if (q.matches("text.messageText") || steps.length === 0) steps.push([q]); else steps[steps.length - 1].push(q); });
      if (steps.length > 1) {
        const stepAt = (i: number) => start + ((end - start) * i) / Math.max(1, steps.length - 1);
        const stepShown = (i: number) => interpolate(frame, [stepAt(i), stepAt(i) + 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        let now = -1;
        steps.forEach((_, i) => { if (stepShown(i) > 0.5) now = i; });
        steps.forEach((group, i) => group.forEach((q) => { q.style.opacity = String(stepShown(i) * (i === now ? 1 : 0.72)); }));
      }
      return;
    }
    // reveal: nodes in the order of the drawing, evenly across the section; an arrow appears with the node it points to
    if (nodes.length < 2) return;
    // Mermaid prefixes every id with a random render id ("t1eag7m-flowchart-A-0", "t1eag7m-L_A_B_0"), so names are read from the end of the id
    const names = nodes.map((n) => ((n.id || "").match(/flowchart-(.+?)-\d+$/) || [])[1] || "");
    // with the camera, a step fades out as the view moves past it (when the step CAMERA_WINDOW later appears), so nothing is ever half cut at the edge
    const leaving = (i: number) => (camera && i + CAMERA_WINDOW < nodes.length ? 1 - shown(i + CAMERA_WINDOW) : 1);
    nodes.forEach((n, i) => {
      n.style.opacity = String(shown(i) * leaving(i) * (i === current ? 1 : 0.8));      // the step being told is fully lit, the earlier ones settle back
      if (i === current) n.setAttribute("data-current", "1"); else n.removeAttribute("data-current");
    });
    const paths = Array.from(el.querySelectorAll<SVGElement>("g.edgePaths path, path.flowchart-link"));
    const labels = Array.from(el.querySelectorAll<SVGElement>("g.edgeLabels > g.edgeLabel"));
    paths.forEach((path, j) => {
      const rest = ((path.id || "").match(/L[_-](.+?)[_-]\d+$/) || [])[1] || "";
      let target = -1, best = 0;
      names.forEach((name, i) => { if (name && rest.endsWith("_" + name) && name.length > best) { target = i; best = name.length; } });
      // a diagram type whose ids carry no names (state diagrams): arrows come in the order they were written, each with the next node
      if (target < 0) target = Math.min(j + 1, nodes.length - 1);
      const o = shown(target) * (camera && target - 1 + CAMERA_WINDOW < nodes.length ? 1 - shown(target - 1 + CAMERA_WINDOW) : 1);
      path.style.opacity = String(o);
      if (labels[j]) labels[j].style.opacity = String(o);
    });
  });
  if (failed) return <>{fallback}</>;       // a diagram that cannot be drawn must never leave an empty panel: the section shows its plain scene
  const cardFill = p.light ? "#ffffff" : "rgba(9, 27, 46, 0.96)";
  const css = `.sf-mmd .node rect, .sf-mmd .node polygon, .sf-mmd .node circle, .sf-mmd .node ellipse, .sf-mmd .node path { fill: ${cardFill} !important; stroke: ${accent} !important; stroke-width: 3px !important; }
    .sf-mmd .node rect { rx: 18px; ry: 18px; }
    .sf-mmd g.node { filter: drop-shadow(0 0 7px ${accent}55); }
    .sf-mmd g.node[data-current="1"] { filter: drop-shadow(0 0 20px ${accent}); }
    .sf-mmd g.node[data-current="1"] rect, .sf-mmd g.node[data-current="1"] polygon, .sf-mmd g.node[data-current="1"] circle { stroke-width: 5px !important; }
    .sf-mmd .edgePath path, .sf-mmd path.flowchart-link, .sf-mmd .messageLine0, .sf-mmd .messageLine1 { stroke: ${accent} !important; stroke-opacity: 0.75; stroke-width: 4px !important; }
    .sf-mmd marker path, .sf-mmd .arrowMarkerPath { fill: ${accent} !important; stroke: ${accent} !important; }
    .sf-mmd text, .sf-mmd .nodeLabel, .sf-mmd .label, .sf-mmd .label div, .sf-mmd .nodeLabel p { fill: ${p.text} !important; color: ${p.text} !important; font-family: ${p.font} !important; font-size: 30px; }
    .sf-mmd foreignObject { overflow: visible !important; }
    .sf-mmd .labelBkg, .sf-mmd .edgeLabel p { background-color: transparent !important; color: ${p.text} !important; }
    .sf-mmd .edgeLabel span { background-color: ${cardFill} !important; color: ${p.text} !important; padding: 2px 12px; border-radius: 10px; font-size: 24px; }
    .sf-mmd .edgeLabel rect, .sf-mmd .edgeLabel .background { fill: transparent !important; opacity: 0 !important; }
    .sf-mmd .cluster rect { fill: ${p.light ? "#00000010" : "#ffffff0a"} !important; stroke: ${p.dim} !important; rx: 18px; }
    .sf-mmd rect.actor { fill: ${cardFill} !important; stroke: ${accent} !important; stroke-width: 3px !important; rx: 14px; }
    .sf-mmd text.actor, .sf-mmd text.actor > tspan { fill: ${p.text} !important; }
    .sf-mmd .messageText { fill: ${p.text} !important; stroke: none !important; }
    .sf-mmd .actor-line { stroke: ${p.dim} !important; stroke-width: 2px !important; }
    .sf-mmd text.noteText, .sf-mmd .noteText > tspan { fill: #0b1f33 !important; }`;
  return (
    <div style={{ width: "100%", height: "100%", boxSizing: "border-box", display: "flex", padding: 30 * u, borderRadius: 26 * u, overflow: "hidden", border: `2px solid ${accent}55`,
      boxShadow: `0 0 ${50 * u}px ${accent}22`, background: p.card, backdropFilter: p.blur }}>
      <div ref={host} className="sf-mmd" style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <style>{css}</style>
        <div dangerouslySetInnerHTML={{ __html: svg }} style={{ display: "flex", alignItems: "center", justifyContent: "center" }} />
      </div>
    </div>
  );
};

const SCENE_VIEWS = { timeline: Timeline, flow: Flow, counters: Counters, checklist: Checklist, terminal: Terminal, quote: Quote, equation: Equation, compare: Compare, chart: Chart, animation: Quote, diagram: Quote } as const;

// one beat of stock footage: it punches in with a flash, drifts to one side, and repeats when the clip is shorter than the beat
const BeatFootage: React.FC<{ src: string; seconds: number; kind?: "video" | "image"; index: number; frames: number; start: number; opacity: number }> = ({ src, seconds, kind, index, frames, start, opacity }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const punch = interpolate(frame, [0, 12], [1.2, 1.04], { extrapolateRight: "clamp" });
  const drift = (frame / Math.max(1, frames)) * 3.5 * (index % 2 === 0 ? 1 : -1);
  const flash = interpolate(frame, [0, 7], [0.5, 0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      {kind === "image" ? (
        <Img src={asset(src)} style={{ width: "100%", height: "100%", objectFit: "cover", opacity, transform: `scale(${punch + frame * 0.0011}) translateX(${drift * 1.4}%)` }} />
      ) : (
        <Loop durationInFrames={Math.max(15, Math.round(seconds * fps))}>
          <OffthreadVideo src={asset(src)} muted startFrom={start} style={{ width: "100%", height: "100%", objectFit: "cover", opacity, transform: `scale(${punch + frame * 0.0006}) translateX(${drift}%)` }} />
        </Loop>
      )}
      <AbsoluteFill style={{ background: "#ffffff", opacity: flash }} />
    </AbsoluteFill>
  );
};

const SectionScene: React.FC<{ index: number; total: number; section: Props["sections"][number]; p: Pal; accent: string; frames: number }> = ({ index, total, section, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, h, portrait } = useUnit();
  const View = SCENE_VIEWS[section.scene];
  const fade = Math.min(interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" }), interpolate(frame, [frames - 10, frames], [1, 0], { extrapolateLeft: "clamp" }));
  const footage = section.footage ?? [];                 // the renderer may hand over props without the schema defaults
  const whole = section.scene === "animation";          // one animation over the whole narration: no heading, no opener, the picture fills the frame
  const beats = section.beats && section.beats.length ? section.beats : [[0, frames / fps] as [number, number]];
  const beatStart = beats.reduce((a, b) => (frame >= Math.round(b[0] * fps) ? Math.round(b[0] * fps) : a), 0);
  const pulse = interpolate(frame - beatStart, [0, 9], [1.035, 1], { extrapolateRight: "clamp" });      // the scene gives a small jolt at every beat
  const push = (1 + 0.05 * (frame / frames)) * pulse;
  const wipe = interpolate(frame, [0, 18], [-30, 115], { extrapolateRight: "clamp" });
  const underline = interpolate(frame, [4, 24], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity: fade }}>
      {footage.length > 0 && (
        <AbsoluteFill>
          {beats.map((b, i) => {
            const clip = footage[i % footage.length];
            const from = Math.round(b[0] * fps);
            const len = Math.max(8, Math.round((b[1] - b[0]) * fps));
            return (
              <Sequence key={i} from={from} durationInFrames={len}>
                <BeatFootage opacity={p.light ? 0.42 : 0.66} src={clip.src} seconds={clip.seconds} kind={clip.kind} index={i} frames={len} start={Math.round((i % 3) * 1.5 * fps) % Math.max(1, Math.round(clip.seconds * fps))} />
              </Sequence>
            );
          })}
          <AbsoluteFill style={{ background: `linear-gradient(180deg, ${p.bg1}b8 0%, ${p.bg1}3d 45%, ${p.bg1}d0 100%)` }} />
          <AbsoluteFill style={{ background: `${accent}14`, mixBlendMode: "color" }} />
          <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)" }} />
        </AbsoluteFill>
      )}
      <AbsoluteFill style={{ padding: whole ? `${50 * u}px ${50 * u}px ${Math.max(270 * u, h * (portrait ? 0.2 : 0.15))}px` : `${80 * u}px ${70 * u}px ${Math.max(300 * u, h * (portrait ? 0.22 : 0.16), captionZone(u, h))}px`, transform: `scale(${whole ? 1 : push})`, transformOrigin: "50% 45%" }}>
        {!whole && <div style={{ marginBottom: 36 * u }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 24 * u }}>
            <div style={{ fontFamily: MONO, fontSize: 34 * u, color: accent, letterSpacing: 2 }}>{String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}</div>
            <div style={{ fontFamily: FONT, fontSize: 60 * u, fontWeight: 800, color: p.text, textTransform: "uppercase", letterSpacing: 1 }}>{section.title}</div>
          </div>
          <div style={{ height: 5 * u, width: `${underline * 38}%`, background: accent, marginTop: 14 * u, borderRadius: 3, boxShadow: `0 0 ${14 * u}px ${accent}` }} />
        </div>}
        <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {section.clip && whole ? (
            <OffthreadVideo src={asset(section.clip)} muted transparent playbackRate={section.clipRate} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
          ) : section.clip ? (
            <div style={{ height: "100%", aspectRatio: portrait ? "4 / 5" : String(section.clipAspect), maxWidth: "100%", borderRadius: 26 * u, overflow: "hidden", border: `2px solid ${accent}55`, boxShadow: `0 0 ${50 * u}px ${accent}22`, background: "rgba(4,10,22,0.45)", backdropFilter: "blur(14px)" }}>
              <OffthreadVideo src={asset(section.clip)} muted transparent playbackRate={section.clipRate} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            </div>
          ) : (
            section.scene === "diagram" && section.diagram ? (
              <MermaidDiagram code={section.diagram} p={p} accent={accent} frames={frames}
                fallback={<AutoFit><Flow labels={section.labels.length ? section.labels : [section.title]} cues={section.cues} p={p} accent={accent} frames={frames} /></AutoFit>} />
            ) : (
              <AutoFit><View labels={section.labels.length ? section.labels : [section.title]} cues={section.cues} p={p} accent={accent} frames={frames} /></AutoFit>
            )
          )}
        </div>
      </AbsoluteFill>
      {(section.sourceLabels ?? []).length > 0 && (
        <div style={{ position: "absolute", right: 56 * u, top: (portrait ? 168 : 44) * u, display: "flex", alignItems: "center", gap: 10 * u, background: p.card, backdropFilter: p.blur, border: `1px solid ${p.line}`, borderRadius: 999, padding: `${8 * u}px ${20 * u}px`, opacity: interpolate(frame, [36, 52], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          <span style={{ fontFamily: MONO, fontSize: 20 * u, color: accent, letterSpacing: 2 }}>SOURCE</span>
          <span style={{ fontFamily: FONT, fontSize: 24 * u, color: p.text }}>{(section.sourceLabels ?? []).join(" · ")}</span>
        </div>
      )}
      {frame < 42 && !whole && (
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", background: `${p.bg1}${frame < 30 ? "d9" : "99"}`, opacity: interpolate(frame, [0, 6, 30, 42], [0, 1, 1, 0], { extrapolateRight: "clamp" }) }}>
          <div style={{ fontFamily: FONT, fontSize: 340 * u, fontWeight: 900, color: "transparent", WebkitTextStroke: `${4 * u}px ${accent}`, lineHeight: 1, transform: `scale(${1 + 0.08 * (frame / 42)})` }}>{String(index + 1).padStart(2, "0")}</div>
          <div style={{ fontFamily: FONT, fontSize: 74 * u, fontWeight: 800, color: p.text, textTransform: "uppercase", letterSpacing: 4 * u, marginTop: 8 * u }}>{section.title}</div>
        </AbsoluteFill>
      )}
      <div style={{ position: "absolute", top: 0, bottom: 0, left: `${wipe}%`, width: "24%", background: `linear-gradient(90deg, transparent, ${accent}40, transparent)`, transform: "skewX(-12deg)", pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};

const Cover: React.FC<{ title: string; p: Pal; accent: string; frames: number; sub?: string; lines?: string[]; hook?: string }> = ({ title, p, accent, frames, sub, lines, hook }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  const t = enter(frame, 2, fps);
  const fade = Math.min(1, interpolate(frame, [frames - 10, frames], [1, 0], { extrapolateLeft: "clamp" }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: `0 ${80 * u}px`, opacity: fade }}>
      <div style={{ width: 120 * u * t, height: 8 * u, background: accent, borderRadius: 4, marginBottom: 40 * u, boxShadow: `0 0 ${24 * u}px ${accent}` }} />
      {hook ? (
        <>
          <div style={{ fontFamily: MONO, fontSize: 36 * u, color: accent, letterSpacing: 2, textTransform: "uppercase", marginBottom: 26 * u, opacity: t }}>{title}</div>
          <div style={{ fontFamily: FONT, fontSize: (hook.length > 60 ? 76 : 96) * u, fontWeight: 800, color: p.text, lineHeight: 1.08, opacity: t, transform: `translateY(${(1 - t) * 40 * u}px)` }}>{hook}</div>
        </>
      ) : (
        <div style={{ fontFamily: FONT, fontSize: 92 * u, fontWeight: 800, color: p.text, lineHeight: 1.08, opacity: t, transform: `translateY(${(1 - t) * 40 * u}px)` }}>{title}</div>
      )}
      {sub && <div style={{ fontFamily: MONO, fontSize: 34 * u, color: accent, marginTop: 36 * u, opacity: t }}>{sub}</div>}
      {lines && lines.map((l, i) => <div key={i} style={{ fontFamily: FONT, fontSize: 32 * u, color: p.dim, marginTop: 14 * u, opacity: t }}>{l}</div>)}
    </AbsoluteFill>
  );
};

// The caption box sits `captionPad` above the bottom edge and can wrap to two lines of 62-unit type inside a padded pill. The scenes reserve
// exactly that much (captionZone), so a long caption can never reach into a scene, whatever its content.
const captionPad = (u: number, h: number) => Math.max(150 * u, h * 0.09);
const captionZone = (u: number, h: number) => captionPad(u, h) + (2 * 62 * 1.25 + 2 * 22 + 28) * u;

// Scales its content down (never up) so that it fits the room it is given: the natural size of the content is measured, so this holds for any
// number of items, any label length and any video shape. A floor keeps the type readable.
const AutoFit: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const outer = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(1);
  useLayoutEffect(() => {
    const o = outer.current, i = inner.current;
    if (!o || !i) return;
    const fit = Math.min(1, o.clientHeight / Math.max(1, i.offsetHeight), o.clientWidth / Math.max(1, i.offsetWidth));
    const next = Math.max(0.3, fit);          // a floor keeps absurd content from vanishing; real content (a handful of short labels) is never near it
    if (Math.abs(next - k) > 0.004) setK(next);
  });
  return (
    <div ref={outer} style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div ref={inner} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${k})`, transformOrigin: "center center" }}>
        {children}
      </div>
    </div>
  );
};

const Captions: React.FC<{ words: Props["words"]; accent: string; pill: string }> = ({ words, accent, pill }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, h } = useUnit();
  const now = frame / fps;
  // chunks of up to 5 words, broken at a pause or sentence end
  const chunks: Props["words"][] = [];
  let cur: Props["words"] = [];
  words.forEach((w, i) => {
    cur.push(w);
    const gap = i + 1 < words.length ? words[i + 1].start - w.end : 1;
    if (cur.length >= 5 || /[.!?]$/.test(w.word) || gap > 0.6) { chunks.push(cur); cur = []; }
  });
  if (cur.length) chunks.push(cur);
  const chunk = chunks.find((c) => now >= c[0].start - 0.05 && now <= c[c.length - 1].end + 0.25);
  if (!chunk) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: captionPad(u, h) }}>
      <div style={{ background: pill, borderRadius: 22 * u, padding: `${22 * u}px ${38 * u}px`, maxWidth: "88%", textAlign: "center" }}>
        {chunk.map((w, i) => {
          const active = now >= w.start && now <= w.end + 0.05;
          return <span key={i} style={{ fontFamily: FONT, fontSize: 62 * u, fontWeight: 800, color: active ? accent : "#ffffff", marginRight: 16 * u, display: "inline-block" }}>{w.word}</span>;
        })}
      </div>
    </AbsoluteFill>
  );
};


export const CaseVideo: React.FC<Props> = (props) => {
  const { fps } = useVideoConfig();
  const p = PALETTES[props.theme];
  const accent = props.accent || p.accent;
  const sections = props.sections;
  const introF = Math.round(props.introSeconds * fps);
  const lastEnd = sections.length ? Math.max(...sections.map((s) => s.end)) : 0;
  const outroStart = Math.round(lastEnd * fps);
  return (
    <AbsoluteFill style={{ backgroundColor: p.bg1, color: p.text, ...({ "--font": p.font, "--mono": p.mono } as React.CSSProperties) }}>
      <Backdrop p={p} accent={accent} />
      {props.audioUrl && <Audio src={asset(props.audioUrl)} />}
      {props.bgMusicUrl && <Audio src={asset(props.bgMusicUrl)} volume={() => props.bgMusicVolume} loop />}
      {introF > 0 && (
        <Sequence durationInFrames={introF}>
          <Cover title={props.title} hook={props.hook} p={p} accent={accent} frames={introF} sub={props.verified ? undefined : "UNVERIFIED - no sources were given"} />
        </Sequence>
      )}
      {sections.map((s, i) => {
        const from = Math.round(s.start * fps);
        const frames = Math.max(15, Math.round(s.end * fps) - from);
        return (
          <Sequence key={i} from={from} durationInFrames={frames}>
            <SectionScene index={i} total={sections.length} section={s} p={p} accent={accent} frames={frames} />
          </Sequence>
        );
      })}
      {props.outroSeconds > 0 && (
        <Sequence from={outroStart} durationInFrames={Math.round(props.outroSeconds * fps)}>
          <Cover title={props.verified ? "Sources" : "Unverified"} p={p} accent={accent} frames={Math.round(props.outroSeconds * fps)}
            lines={props.verified
              ? [...props.sources.slice(0, 3), ...(props.removedClaims > 0 ? [`${props.removedClaims} sentence${props.removedClaims === 1 ? "" : "s"} left out: the sources do not hold ${props.removedClaims === 1 ? "it" : "them"}.`] : ["Every figure and name was found in the sources."])]
              : ["No sources were given. Check the facts before you rely on them."]} />
        </Sequence>
      )}
      {!props.captionsOff && <Captions words={props.words} accent={p.cap && !props.accent ? p.cap : accent} pill={p.light ? "rgba(10,10,14,0.86)" : "rgba(0,0,0,0.62)"} />}
    </AbsoluteFill>
  );
};
