// "CaseVideo": a sectioned explainer. Every section of the script is one scene (timeline, flow, counters, checklist, terminal, quote)
// drawn from its on-screen labels, over a themed background, with word-timed captions. No custom fonts (a font load stalled the CI
// renderer before), no stock footage: everything is drawn, so a run needs no key and no download.
import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { z } from "zod";

export const CASE_THEMES = ["dark", "clean", "warm"] as const;
export const CASE_SCENES = ["timeline", "flow", "counters", "checklist", "terminal", "quote"] as const;

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
    start: z.number(),
    end: z.number(),
  })).default([]),
  words: z.array(z.object({ word: z.string(), start: z.number(), end: z.number() })).default([]),
});
type Props = z.infer<typeof caseVideoSchema>;

const PALETTES = {
  dark: { bg1: "#05070d", bg2: "#0b1220", text: "#e8f1ff", dim: "#7d8ba3", accent: "#00e5a8", card: "rgba(14,24,42,0.78)", line: "rgba(0,229,168,0.22)" },
  clean: { bg1: "#f4f6fb", bg2: "#e3e9f5", text: "#101828", dim: "#5b6578", accent: "#2563eb", card: "rgba(255,255,255,0.85)", line: "rgba(37,99,235,0.2)" },
  warm: { bg1: "#1d1410", bg2: "#2b1d15", text: "#fff3e6", dim: "#c3a58c", accent: "#ff8a3d", card: "rgba(60,38,26,0.8)", line: "rgba(255,138,61,0.25)" },
} as const;
const FONT = '"Segoe UI", "Helvetica Neue", Arial, "Noto Sans", sans-serif';
const MONO = '"Cascadia Mono", Consolas, "SF Mono", "DejaVu Sans Mono", monospace';

const useUnit = () => {
  const { width, height } = useVideoConfig();
  return { u: Math.min(width, height) / 1080, w: width, h: height, portrait: height > width };
};

const Background: React.FC<{ p: (typeof PALETTES)[keyof typeof PALETTES]; dark: boolean }> = ({ p, dark }) => {
  const frame = useCurrentFrame();
  const { u } = useUnit();
  const drift = (frame * 0.4) % (80 * u);
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 30% 20%, ${p.bg2}, ${p.bg1} 70%)` }}>
      <AbsoluteFill style={{
        backgroundImage: `linear-gradient(${p.line} 1px, transparent 1px), linear-gradient(90deg, ${p.line} 1px, transparent 1px)`,
        backgroundSize: `${80 * u}px ${80 * u}px`, backgroundPosition: `${drift}px ${drift}px`, opacity: dark ? 0.35 : 0.5,
        maskImage: "radial-gradient(ellipse at center, black 30%, transparent 85%)", WebkitMaskImage: "radial-gradient(ellipse at center, black 30%, transparent 85%)",
      }} />
      {dark && <AbsoluteFill style={{ background: "repeating-linear-gradient(0deg, rgba(255,255,255,0.025) 0px, rgba(255,255,255,0.025) 1px, transparent 2px, transparent 4px)" }} />}
    </AbsoluteFill>
  );
};

const enter = (frame: number, delay: number, fps: number) =>
  spring({ frame: frame - delay, fps, config: { damping: 18, stiffness: 120 } });

type Pal = (typeof PALETTES)[keyof typeof PALETTES];
type SceneProps = { labels: string[]; p: Pal; accent: string; frames: number };

// the labels appear one after another across the first 70% of the section
const stagger = (i: number, n: number, frames: number) => Math.round((i / Math.max(1, n)) * frames * 0.7) + 6;

const Timeline: React.FC<SceneProps> = ({ labels, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
  return (
    <div style={{ display: "flex", flexDirection: portrait ? "column" : "row", gap: 36 * u, alignItems: portrait ? "flex-start" : "stretch", justifyContent: "center", width: "100%" }}>
      {labels.map((l, i) => {
        const t = enter(frame, stagger(i, labels.length, frames), fps);
        return (
          <div key={i} style={{ display: "flex", flexDirection: portrait ? "row" : "column", alignItems: "center", gap: 22 * u, opacity: t, transform: `translate${portrait ? "X" : "Y"}(${(1 - t) * 40 * u}px)`, flex: portrait ? undefined : 1 }}>
            <div style={{ width: 34 * u, height: 34 * u, borderRadius: "50%", background: accent, boxShadow: `0 0 ${24 * u}px ${accent}`, flexShrink: 0 }} />
            <div style={{ fontFamily: FONT, fontSize: 46 * u, fontWeight: 700, color: p.text, lineHeight: 1.15, textAlign: portrait ? "left" : "center" }}>{l}</div>
          </div>
        );
      })}
    </div>
  );
};

const Flow: React.FC<SceneProps> = ({ labels, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
  return (
    <div style={{ display: "flex", flexDirection: portrait ? "column" : "row", alignItems: "center", justifyContent: "center", gap: 18 * u, width: "100%" }}>
      {labels.map((l, i) => {
        const t = enter(frame, stagger(i, labels.length, frames), fps);
        return (
          <React.Fragment key={i}>
            {i > 0 && <div style={{ color: accent, fontSize: 54 * u, fontFamily: FONT, opacity: t, transform: portrait ? "rotate(90deg)" : undefined }}>➜</div>}
            <div style={{ background: p.card, border: `2px solid ${accent}`, borderRadius: 22 * u, padding: `${28 * u}px ${34 * u}px`, fontFamily: FONT, fontSize: 40 * u, fontWeight: 700, color: p.text, textAlign: "center", opacity: t, transform: `scale(${0.85 + 0.15 * t})`, boxShadow: `0 0 ${30 * u}px ${accent}33`, maxWidth: portrait ? 860 * u : 420 * u }}>
              {l}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
};

// "5,078 flights cancelled" -> count the number up, show the words under it
const splitNumber = (label: string) => {
  const m = label.match(/(\$?\s?\d[\d,.]*\s?(?:%|[kKmMbB]\b|million|billion|trillion)?)/);
  if (!m) return null;
  const raw = m[1].trim();
  const num = parseFloat(raw.replace(/[^\d.]/g, "").replace(/\.(?=.*\.)/g, ""));
  if (!isFinite(num)) return null;
  const rest = (label.slice(0, m.index) + " " + label.slice((m.index || 0) + m[1].length)).replace(/\s+/g, " ").trim();
  return { raw, num, rest, prefix: raw.startsWith("$") ? "$" : "", suffix: raw.replace(/^\$?\s?[\d,.]+/, "").trim() };
};

const Counters: React.FC<SceneProps> = ({ labels, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u, portrait } = useUnit();
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 28 * u, justifyContent: "center", width: "100%" }}>
      {labels.map((l, i) => {
        const delay = stagger(i, labels.length, frames);
        const t = enter(frame, delay, fps);
        const parts = splitNumber(l);
        const progress = interpolate(frame - delay, [0, 40], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const decimals = parts && /\.\d/.test(parts.raw) ? (parts.raw.split(".")[1].match(/^\d+/) || [""])[0].length : 0;
        const shown = parts ? (parts.num * progress).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : null;
        return (
          <div key={i} style={{ background: p.card, border: `1px solid ${p.line}`, borderTop: `4px solid ${accent}`, borderRadius: 20 * u, padding: `${30 * u}px ${36 * u}px`, minWidth: (portrait ? 800 : 440) * u, textAlign: "center", opacity: t, transform: `translateY(${(1 - t) * 40 * u}px)` }}>
            {parts ? (
              <>
                <div style={{ fontFamily: FONT, fontSize: 92 * u, fontWeight: 800, color: accent, lineHeight: 1 }}>{parts.prefix}{shown}{parts.suffix ? ` ${parts.suffix}` : ""}</div>
                <div style={{ fontFamily: FONT, fontSize: 38 * u, color: p.text, marginTop: 12 * u }}>{parts.rest}</div>
              </>
            ) : (
              <div style={{ fontFamily: FONT, fontSize: 52 * u, fontWeight: 700, color: p.text }}>{l}</div>
            )}
          </div>
        );
      })}
    </div>
  );
};

const Checklist: React.FC<SceneProps> = ({ labels, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 26 * u, width: "100%", maxWidth: 1400 * u }}>
      {labels.map((l, i) => {
        const delay = stagger(i, labels.length, frames);
        const t = enter(frame, delay, fps);
        const tick = interpolate(frame - delay - 8, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 28 * u, background: p.card, border: `1px solid ${p.line}`, borderRadius: 18 * u, padding: `${24 * u}px ${30 * u}px`, opacity: t, transform: `translateX(${(1 - t) * -60 * u}px)` }}>
            <div style={{ width: 52 * u, height: 52 * u, borderRadius: 12 * u, border: `3px solid ${accent}`, display: "flex", alignItems: "center", justifyContent: "center", color: accent, fontSize: 40 * u, fontFamily: FONT, fontWeight: 800, flexShrink: 0 }}>
              <span style={{ opacity: tick, transform: `scale(${0.4 + 0.6 * tick})` }}>✓</span>
            </div>
            <div style={{ fontFamily: FONT, fontSize: 44 * u, fontWeight: 600, color: p.text }}>{l}</div>
          </div>
        );
      })}
    </div>
  );
};

const Terminal: React.FC<SceneProps> = ({ labels, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { u } = useUnit();
  const per = Math.max(8, Math.floor((frames * 0.7) / Math.max(1, labels.length)));
  return (
    <div style={{ background: "rgba(2,6,12,0.9)", border: `1px solid ${accent}55`, borderRadius: 18 * u, padding: 36 * u, width: "100%", maxWidth: 1400 * u, fontFamily: MONO, boxShadow: `0 0 ${40 * u}px ${accent}22` }}>
      {labels.map((l, i) => {
        const chars = Math.max(0, Math.min(l.length, Math.floor(((frame - 6 - i * per) / per) * l.length * 1.4)));
        return (
          <div key={i} style={{ fontSize: 40 * u, color: p.text === "#101828" ? "#101828" : "#9fffd9", marginBottom: 18 * u, minHeight: 48 * u }}>
            <span style={{ color: accent }}>$ </span>{l.slice(0, chars)}{chars < l.length && chars > 0 ? <span style={{ opacity: frame % 20 < 10 ? 1 : 0 }}>▌</span> : null}
          </div>
        );
      })}
    </div>
  );
};

const Quote: React.FC<SceneProps> = ({ labels, p, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { u } = useUnit();
  const t = enter(frame, 4, fps);
  return (
    <div style={{ borderLeft: `${10 * u}px solid ${accent}`, paddingLeft: 40 * u, opacity: t, transform: `translateY(${(1 - t) * 30 * u}px)`, maxWidth: 1400 * u }}>
      {labels.map((l, i) => <div key={i} style={{ fontFamily: FONT, fontSize: (i === 0 ? 72 : 44) * u, fontWeight: i === 0 ? 800 : 500, color: i === 0 ? p.text : p.dim, lineHeight: 1.2, marginBottom: 16 * u }}>{l}</div>)}
    </div>
  );
};

const SCENE_VIEWS = { timeline: Timeline, flow: Flow, counters: Counters, checklist: Checklist, terminal: Terminal, quote: Quote } as const;

const SectionScene: React.FC<{ index: number; total: number; section: Props["sections"][number]; p: Pal; accent: string; frames: number }> = ({ index, total, section, p, accent, frames }) => {
  const frame = useCurrentFrame();
  const { u, h } = useUnit();
  const View = SCENE_VIEWS[section.scene];
  const fade = Math.min(interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" }), interpolate(frame, [frames - 10, frames], [1, 0], { extrapolateLeft: "clamp" }));
  return (
    <AbsoluteFill style={{ opacity: fade, padding: `${90 * u}px ${70 * u}px ${Math.max(360 * u, h * 0.2)}px` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 24 * u, marginBottom: 54 * u }}>
        <div style={{ fontFamily: MONO, fontSize: 34 * u, color: accent, letterSpacing: 2 }}>{String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}</div>
        <div style={{ fontFamily: FONT, fontSize: 56 * u, fontWeight: 800, color: p.text, textTransform: "uppercase", letterSpacing: 1 }}>{section.title}</div>
      </div>
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <View labels={section.labels.length ? section.labels : [section.title]} p={p} accent={accent} frames={frames} />
      </div>
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

const asset = (url: string) => (/^(https?:|data:)/.test(url) ? url : staticFile(url));

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
      <Background p={p} dark={props.theme !== "clean"} />
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
