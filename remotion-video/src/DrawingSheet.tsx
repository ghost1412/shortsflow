// "DrawingSheet": the drawings a text model just made, numbered on one picture, so that an image-reading model can be asked what each one shows
// (engine/story_objects.py). Rendered as a single still frame.
import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { z } from "zod";

export const drawingSheetSchema = z.object({ items: z.array(z.string()).default([]) });   // data: URIs of the drawings
export const SHEET_COLUMNS = 3;
export const SHEET_CELL = 360;

export const DrawingSheet: React.FC<z.infer<typeof drawingSheetSchema>> = ({ items }) => (
  <AbsoluteFill style={{ backgroundColor: "#2b2036", flexDirection: "row", flexWrap: "wrap", alignContent: "flex-start" }}>
    {items.map((src, i) => (
      <div key={i} style={{ width: SHEET_CELL, height: SHEET_CELL, boxSizing: "border-box", border: "2px solid #6b5a80", position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ position: "absolute", left: 14, top: 8, fontFamily: "Arial, sans-serif", fontSize: 44, fontWeight: 700, color: "#ffffff" }}>{i + 1}</div>
        <Img src={src} style={{ width: 280, height: 280, marginTop: 24 }} />
      </div>
    ))}
  </AbsoluteFill>
);
