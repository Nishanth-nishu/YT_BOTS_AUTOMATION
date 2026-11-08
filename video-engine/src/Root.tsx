import React from "react";
import { Composition, Folder, Still } from "remotion";
import { SmokeTest } from "./compositions/SmokeTest";
import { Reel, calculateReelMetadata } from "./compositions/Reel";
import { Cover } from "./compositions/Cover";
import { SceneLibrary, SAMPLES } from "./compositions/SceneLibrary";
import { video } from "./design/tokens";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="Reels">
        <Composition
          id="Reel"
          component={Reel}
          durationInFrames={30 * video.fps}
          fps={video.fps}
          width={video.width}
          height={video.height}
          calculateMetadata={calculateReelMetadata}
          defaultProps={{
            specFile: "specs/agents-benchmark.json",
            spec: null,
            quality: "standard",
          }}
        />
        <Still
          id="Cover"
          component={Cover}
          width={video.width}
          height={video.height}
          defaultProps={{
            title: "How AI agents actually work",
            kicker: "AI EXPLAINED / 01",
            styleId: "cinematic",
            highlight: ["agents"],
          }}
        />
      </Folder>
      <Folder name="Library">
        {Object.entries(SAMPLES).map(([name, sample]) => (
          <Composition
            key={name}
            id={`Lib-${name}`}
            component={SceneLibrary}
            durationInFrames={6 * video.fps}
            fps={video.fps}
            width={video.width}
            height={video.height}
            defaultProps={{
              kind: sample.kind ?? "concept",
              styleId: "explainer",
              title: sample.title ?? "",
              highlight: sample.highlight ?? [],
              lines: sample.lines ?? [],
              data: sample.data ?? {},
              cta: null,
              durationSeconds: 6,
            }}
          />
        ))}
      </Folder>
      <Folder name="System">
        <Composition
          id="SmokeTest"
          component={SmokeTest}
          durationInFrames={6 * video.fps}
          fps={video.fps}
          width={video.width}
          height={video.height}
          defaultProps={{
            title: "The engine can render",
            styleId: "cinematic",
          }}
        />
      </Folder>
    </>
  );
};
