import "./index.css";
import { Composition } from "remotion";
import { ShortFlow, shortFlowSchema } from "./ShortFlow";
import { OverlayOnly, overlaySchema } from "./overlay";
import { CaseVideo, caseVideoSchema } from "./CaseVideo";
import { PresenterCard, presenterCardSchema } from "./Presenter";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ShortFlow"
        component={ShortFlow}
        fps={30}
        width={1080}
        height={1920}
        schema={shortFlowSchema}
        calculateMetadata={({ props }) => {
          let durationInFrames = 900;
          if (props.words && props.words.length > 0) {
            const maxWordEnd = Math.max(...props.words.map(w => w.end));
            durationInFrames = Math.ceil((maxWordEnd + 1.0) * 30);
          }
          if (props.backgrounds && props.backgrounds.length > 0) {
            const maxBgEnd = Math.max(...props.backgrounds.map(bg => bg.end));
            const bgDurationFrames = Math.ceil(maxBgEnd * 30);
            if (bgDurationFrames > durationInFrames) {
              durationInFrames = bgDurationFrames;
            }
          }
          return {
            durationInFrames: Math.max(30, durationInFrames),
          };
        }}
        defaultProps={{
          audioUrl: "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
          bgMusicUrl: undefined,
          bgMusicVolume: 0.15,
          mode: "FACTS" as const,
          category: "general",
          titleText: "Preview Short",
          subtitleYPos: 1600,
          captionSize: 1,
          captionsOff: false,
          captionStyle: "HORMOZI" as const,
          captionEmoji: false,
          hookSeconds: 2.8,
          words: [
            { word: "This", start: 0.1, end: 0.5 },
            { word: "is", start: 0.5, end: 0.9 },
            { word: "a", start: 0.9, end: 1.2 },
            { word: "preview", start: 1.2, end: 2.0 },
            { word: "subtitle", start: 2.0, end: 3.0 },
          ],
          backgrounds: [],
        }}
      />
      <Composition
        id="Overlay"
        component={OverlayOnly}
        fps={30}
        width={1080}
        height={1920}
        schema={overlaySchema}
        calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.ceil(props.seconds * 30)) })}
        defaultProps={{ hookSeconds: 0, seconds: 3, clockOffset: 0, clockTotal: 10 }}
      />
      <Composition
        id="CaseVideo"
        component={CaseVideo}
        fps={30}
        width={1920}
        height={1080}
        schema={caseVideoSchema}
        calculateMetadata={({ props }) => {
          const end = props.sections.length ? Math.max(...props.sections.map((s) => s.end)) : 5;
          return { durationInFrames: Math.max(30, Math.ceil((end + props.outroSeconds) * 30)) };
        }}
        defaultProps={{
          title: "Preview",
          theme: "dark" as const,
          bgMusicVolume: 0.12,
          introSeconds: 2.5,
          hook: "",
          outroSeconds: 3,
          verified: true,
          removedClaims: 0,
          sources: [],
          captionsOff: false,
          sections: [
            { title: "What happened", scene: "timeline" as const, labels: ["First", "Second", "Third"], cues: [], clipRate: 1, clipAspect: 16 / 9, sourceLabels: [], footage: [], beats: [], start: 2.5, end: 8 },
          ],
          words: [],
          transition: "number" as const,
        }}
      />
      <Composition
        id="PresenterCard"
        component={PresenterCard}
        fps={30}
        width={340}
        height={400}
        durationInFrames={90}
        schema={presenterCardSchema}
        calculateMetadata={({ props }) => ({ durationInFrames: Math.max(90, Math.ceil(((props.words.length ? Math.max(...props.words.map((w) => w.end)) : 0) + 0.6) * 30)) })}
        defaultProps={{ avatar: { kind: "human" as const, name: "Alex", skin: "#f1c3a0", hair: "short" as const, hairColor: "#2b1d15", eyeColor: "#3b6fd8",
                                  beard: "none" as const, glasses: "none" as const, lashes: false, lips: "#b0505a", outfit: "#ff8a3d", pattern: "plain" as const,
                                  furLight: "#fff4e8" }, words: [], accent: "#00e5a8" }}
      />
    </>
  );
};
