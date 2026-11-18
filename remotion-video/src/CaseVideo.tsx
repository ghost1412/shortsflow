// "CaseVideo": a sectioned explainer. Every section of the script is one scene (timeline, flow, counters, checklist, terminal, quote)
// drawn from its on-screen labels, over a themed background, with word-timed captions. No custom fonts (a font load stalled the CI
// renderer before), no stock footage: everything is drawn, so a run needs no key and no download.
import React from "react";
import { AbsoluteFill, Audio, Loop, OffthreadVideo, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import katex from "katex";
import { z } from "zod";

export const CASE_THEMES = ["dark", "clean", "warm"] as const;
export const CASE_SCENES = ["timeline", "flow", "counters", "checklist", "terminal", "quote", "equation"] as const;

export const caseVideoSchema = z.object({
  title: z.string().default("Explainer"),
  theme: z.enum(CASE_THEMES).default("dark"),
  accent: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
  audioUrl: z.string().optional(),
  bgMusicUrl: z.string().optional(),
  bgMusicVolume: z.number().default(0.12),
  introSeconds: z.number().default(2.5),
  outroSeconds: z.number().default(3),
  verified: z.boolean().default(true),
  sources: z.array(z.string()).default([]),
  captionsOff: z.boolean().default(false),
  sections: z.array(z.object({
    title: z.string(),
    scene: z.enum(CASE_SCENES).default("quote"),
    labels: z.array(z.string()).default([]),
    footage: z.string().optional(),             // stock footage shown dimmed behind the section
    footageSeconds: z.number().default(10),     // its length, so a short clip repeats for the whole section
    clip: z.string().optional(),                // a rendered animation (Manim) drawn for this section, shown instead of the plain scene
    clipRate: z.number().default(1),
    cues: z.array(z.number()).default([]),     // seconds after the section starts at which each label is spoken
    start: z.number(),
    end: z.number(),
  })).default([]),
  words: z.array(z.object({ word: z.string(), start: z.number(), end: z.number() })).default([]),
});
type Props = z.infer<typeof caseVideoSchema>;

const PALETTES = {
  dark: { bg1: "#07101f", bg2: "#12294d", text: "#e8f1ff", dim: "#8fa0bd", accent: "#00e5a8", card: "rgba(16,30,54,0.82)", line: "rgba(0,229,168,0.32)" },
  clean: { bg1: "#eef2fa", bg2: "#d5e0f5", text: "#101828", dim: "#5b6578", accent: "#2563eb", card: "rgba(255,255,255,0.85)", line: "rgba(37,99,235,0.2)" },
  warm: { bg1: "#241711", bg2: "#46291a", text: "#fff3e6", dim: "#c3a58c", accent: "#ff8a3d", card: "rgba(60,38,26,0.8)", line: "rgba(255,138,61,0.25)" },
} as const;
const FONT = '"Segoe UI", "Helvetica Neue", Arial, "Noto Sans", sans-serif';
const MONO = '"Cascadia Mono", Consolas, "SF Mono", "DejaVu Sans Mono", monospace';

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

const Background: React.FC<{ p: (typeof PALETTES)[keyof typeof PALETTES]; dark: boolean; accent: string }> = ({ p, dark, accent }) => {
  const frame = useCurrentFrame();
  const { u } = useUnit();
  const drift = (frame * 0.4) % (80 * u);
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 30% 20%, ${p.bg2}, ${p.bg1} 70%)` }}>
      <AbsoluteFill style={{ background: `radial-gradient(circle at ${50 + 30 * Math.sin(frame / 90)}% ${45 + 25 * Math.cos(frame / 120)}%, ${accent}30, transparent 45%), radial-gradient(circle at ${75 - 25 * Math.cos(frame / 100)}% ${70 - 20 * Math.sin(frame / 80)}%, #3b82f630, transparent 40%)` }} />
      <AbsoluteFill style={{
        backgroundImage: `linear-gradient(${p.line} 1px, transparent 1px), linear-gradient(90deg, ${p.line} 1px, transparent 1px)`,
        backgroundSize: `${80 * u}px ${80 * u}px`, backgroundPosition: `${drift}px ${drift}px`, opacity: dark ? 0.6 : 0.5,
        maskImage: "radial-gradient(ellipse at center, black 30%, transparent 85%)", WebkitMaskImage: "radial-gradient(ellipse at center, black 30%, transparent 85%)",
      }} />
      <Network accent={accent} />
      {dark && <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(255,255,255,0.025) 0px, rgba(255,255,255,0.025) 1px, transparent 2px, transparent 4px)" }} />}
    </AbsoluteFill>
  );
};

const enter = (frame: number, delay: number, fps: number) =>
  spring({ frame: frame - delay, fps, config: { damping: 18, stiffness: 120 } });

type Pal = (typeof PALETTES)[keyof typeof PALETTES];
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
            <div style={{ position: "absolute", left: portrait ? x + 70 * u : x - 230 * u, top: portrait ? y - 34 * u : above ? y - 200 * u : y + 64 * u, width: portrait ? aw - x - 70 * u : 460 * u, textAlign: portrait ? "left" : "center", fontFamily: FONT, fontSize: 44 * u, fontWeight: 700, lineHeight: 1.15, color: i <= act ? p.text : p.dim, opacity: t, transformOrigin: portrait ? "left center" : "center", transform: `translateY(${(1 - t) * (above ? 30 : -30) * u}px) scale(${on ? 1.06 : 1})` }}>{l}</div>
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
          <div key={i} style={{ position: "absolute", left: x - nw / 2, top: y - nh / 2, width: nw, height: nh, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", boxSizing: "border-box", padding: 14 * u, background: p.card, backdropFilter: "blur(16px)", border: `${on ? 4 : 2}px solid ${i <= act ? accent : p.line}`, borderRadius: 22 * u, fontFamily: FONT, fontSize: 38 * u, fontWeight: 700, color: p.text, opacity: t, transform: `scale(${(0.85 + 0.15 * t) * (on ? 1.05 : 1)})`, boxShadow: glow(on, accent, u), flexDirection: "column", gap: 10 * u }}>
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
  const m = label.match(/(\$?\s?\d[\d,.]*\+?\s?(?:%|[kKmMbB]\b|[Mm]illion|[Bb]illion|[Tt]rillion)?)/);
  if (!m) return null;
  const raw = m[1].trim();
  const num = parseFloat(raw.replace(/[^\d.]/g, "").replace(/\.(?=.*\.)/g, ""));
  if (!isFinite(num)) return null;
  const rest = (label.slice(0, m.index) + " " + label.slice((m.index || 0) + m[1].length)).replace(/\s+/g, " ").trim();
  return { raw, num, rest, prefix: raw.startsWith("$") ? "$" : "", suffix: raw.replace(/^\$?\s?[\d,.]+/, "").trim() };
};

const Counters: React.FC<SceneProps> = ({ labels, cues, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
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
          <div key={i} style={{ background: p.card, backdropFilter: "blur(16px)", border: `1px solid ${p.line}`, borderTop: `5px solid ${accent}`, borderRadius: 22 * u, padding: `${26 * u}px ${34 * u}px`, minWidth: (portrait ? 800 : 480) * u, textAlign: "center", display: "flex", flexDirection: "column", justifyContent: "center", opacity: t, transform: `translateY(${(1 - t) * 50 * u}px) scale(${on ? 1.05 : 1})`, boxShadow: glow(on, accent, u) }}>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 10 * u }}><Icon name={iconFor(l)} size={56 * u} color={accent} /></div>
            {parts ? (
              <>
                <div style={{ fontFamily: FONT, fontSize: 96 * u, fontWeight: 800, color: accent, lineHeight: 1 }}>{parts.prefix}{shown}{parts.suffix ? (/^[+%]/.test(parts.suffix) ? parts.suffix : ` ${parts.suffix}`) : ""}</div>
                <div style={{ fontFamily: FONT, fontSize: 42 * u, color: p.text, marginTop: 14 * u }}>{parts.rest}</div>
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
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 * u, width: "100%", maxWidth: 1400 * u }}>
      {labels.map((l, i) => {
        const delay = at[i];
        const t = enter(frame, delay, fps);
        const tick = interpolate(frame - delay - 8, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const on = i === act;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 30 * u, background: p.card, backdropFilter: "blur(16px)", border: `${on ? 3 : 1}px solid ${on ? accent : p.line}`, borderRadius: 20 * u, padding: `${26 * u}px ${32 * u}px`, opacity: t, transform: `translateX(${(1 - t) * -80 * u}px) scale(${on ? 1.03 : 1})`, transformOrigin: "left center", boxShadow: glow(on, accent, u) }}>
            <div style={{ width: 58 * u, height: 58 * u, borderRadius: 14 * u, border: `3px solid ${accent}`, background: tick > 0.5 ? `${accent}33` : "transparent", display: "flex", alignItems: "center", justifyContent: "center", color: accent, fontSize: 44 * u, fontFamily: FONT, fontWeight: 800, flexShrink: 0 }}>
              <span style={{ opacity: tick, transform: `scale(${0.4 + 0.6 * tick})` }}>✓</span>
            </div>
            <div style={{ fontFamily: FONT, fontSize: 48 * u, fontWeight: 600, color: p.text }}>{l}</div>
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
          <div key={i} style={{ background: p.card, backdropFilter: "blur(16px)", border: `${on ? 3 : 1}px solid ${on ? accent : p.line}`, borderRadius: 22 * u, padding: `${22 * u}px ${48 * u}px`, opacity: t, transform: `scale(${(0.9 + 0.1 * t) * (on ? 1.04 : 1)})`, boxShadow: glow(on, accent, u), color: p.text, fontFamily: FONT, fontSize: 78 * u, fontWeight: 600 }}>
            {html ? <span dangerouslySetInnerHTML={{ __html: html }} /> : l}
          </div>
        );
      })}
    </div>
  );
};

const SCENE_VIEWS = { timeline: Timeline, flow: Flow, counters: Counters, checklist: Checklist, terminal: Terminal, quote: Quote, equation: Equation } as const;

const SectionScene: React.FC<{ index: number; total: number; section: Props["sections"][number]; p: Pal; accent: string; frames: number }> = ({ index, total, section, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, h, portrait } = useUnit();
  const View = SCENE_VIEWS[section.scene];
  const fade = Math.min(interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" }), interpolate(frame, [frames - 10, frames], [1, 0], { extrapolateLeft: "clamp" }));
  const push = 1 + 0.05 * (frame / frames);            // a slow push-in over the whole section
  const wipe = interpolate(frame, [0, 18], [-30, 115], { extrapolateRight: "clamp" });
  const underline = interpolate(frame, [4, 24], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity: fade }}>
      {section.footage && (
        <AbsoluteFill>
          <Loop durationInFrames={Math.max(15, Math.round(section.footageSeconds * fps))}>
            <OffthreadVideo src={asset(section.footage)} muted style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.62, transform: `scale(${1 + 0.06 * (frame / frames)})` }} />
          </Loop>
          <AbsoluteFill style={{ background: `linear-gradient(180deg, ${p.bg1}b8 0%, ${p.bg1}3d 45%, ${p.bg1}d0 100%)` }} />
          <AbsoluteFill style={{ background: `${accent}14`, mixBlendMode: "color" }} />
          <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)" }} />
        </AbsoluteFill>
      )}
      <AbsoluteFill style={{ padding: `${80 * u}px ${70 * u}px ${Math.max(300 * u, h * (portrait ? 0.22 : 0.16))}px`, transform: `scale(${push})`, transformOrigin: "50% 45%" }}>
        <div style={{ marginBottom: 36 * u }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 24 * u }}>
            <div style={{ fontFamily: MONO, fontSize: 34 * u, color: accent, letterSpacing: 2 }}>{String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}</div>
            <div style={{ fontFamily: FONT, fontSize: 60 * u, fontWeight: 800, color: p.text, textTransform: "uppercase", letterSpacing: 1 }}>{section.title}</div>
          </div>
          <div style={{ height: 5 * u, width: `${underline * 38}%`, background: accent, marginTop: 14 * u, borderRadius: 3, boxShadow: `0 0 ${14 * u}px ${accent}` }} />
        </div>
        <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {section.clip ? (
            <div style={{ height: "100%", aspectRatio: portrait ? "4 / 5" : "16 / 9", maxWidth: "100%", borderRadius: 26 * u, overflow: "hidden", border: `2px solid ${accent}55`, boxShadow: `0 0 ${50 * u}px ${accent}22`, background: "rgba(4,10,22,0.45)", backdropFilter: "blur(14px)" }}>
              <OffthreadVideo src={asset(section.clip)} muted transparent playbackRate={section.clipRate} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            </div>
          ) : (
            <View labels={section.labels.length ? section.labels : [section.title]} cues={section.cues} p={p} accent={accent} frames={frames} />
          )}
        </div>
      </AbsoluteFill>
      {frame < 42 && (
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", background: `${p.bg1}${frame < 30 ? "d9" : "99"}`, opacity: interpolate(frame, [0, 6, 30, 42], [0, 1, 1, 0], { extrapolateRight: "clamp" }) }}>
          <div style={{ fontFamily: FONT, fontSize: 340 * u, fontWeight: 900, color: "transparent", WebkitTextStroke: `${4 * u}px ${accent}`, lineHeight: 1, transform: `scale(${1 + 0.08 * (frame / 42)})` }}>{String(index + 1).padStart(2, "0")}</div>
          <div style={{ fontFamily: FONT, fontSize: 74 * u, fontWeight: 800, color: p.text, textTransform: "uppercase", letterSpacing: 4 * u, marginTop: 8 * u }}>{section.title}</div>
        </AbsoluteFill>
      )}
      <div style={{ position: "absolute", top: 0, bottom: 0, left: `${wipe}%`, width: "24%", background: `linear-gradient(90deg, transparent, ${accent}40, transparent)`, transform: "skewX(-12deg)", pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};

const Cover: React.FC<{ title: string; p: Pal; accent: string; frames: number; sub?: string; lines?: string[] }> = ({ title, p, accent, frames, sub, lines }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  const t = enter(frame, 2, fps);
  const fade = Math.min(1, interpolate(frame, [frames - 10, frames], [1, 0], { extrapolateLeft: "clamp" }));
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: `0 ${80 * u}px`, opacity: fade }}>
      <div style={{ width: 120 * u * t, height: 8 * u, background: accent, borderRadius: 4, marginBottom: 40 * u, boxShadow: `0 0 ${24 * u}px ${accent}` }} />
      <div style={{ fontFamily: FONT, fontSize: 92 * u, fontWeight: 800, color: p.text, lineHeight: 1.08, opacity: t, transform: `translateY(${(1 - t) * 40 * u}px)` }}>{title}</div>
      {sub && <div style={{ fontFamily: MONO, fontSize: 34 * u, color: accent, marginTop: 36 * u, opacity: t }}>{sub}</div>}
      {lines && lines.map((l, i) => <div key={i} style={{ fontFamily: FONT, fontSize: 32 * u, color: p.dim, marginTop: 14 * u, opacity: t }}>{l}</div>)}
    </AbsoluteFill>
  );
};

const Captions: React.FC<{ words: Props["words"]; accent: string }> = ({ words, accent }) => {
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
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: Math.max(150 * u, h * 0.09) }}>
      <div style={{ background: "rgba(0,0,0,0.62)", borderRadius: 22 * u, padding: `${22 * u}px ${38 * u}px`, maxWidth: "88%", textAlign: "center" }}>
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
    <AbsoluteFill style={{ backgroundColor: p.bg1 }}>
      <Background p={p} dark={props.theme !== "clean"} accent={accent} />
      {props.audioUrl && <Audio src={asset(props.audioUrl)} />}
      {props.bgMusicUrl && <Audio src={asset(props.bgMusicUrl)} volume={() => props.bgMusicVolume} loop />}
      {introF > 0 && (
        <Sequence durationInFrames={introF}>
          <Cover title={props.title} p={p} accent={accent} frames={introF} sub={props.verified ? undefined : "UNVERIFIED - no sources were given"} />
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
            lines={props.verified ? props.sources.slice(0, 3) : ["No sources were given. Check the facts before you rely on them."]} />
        </Sequence>
      )}
      {!props.captionsOff && <Captions words={props.words} accent={accent} />}
    </AbsoluteFill>
  );
};
