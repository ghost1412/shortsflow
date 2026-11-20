// Checks Mermaid source read from stdin without a browser (jsdom gives Mermaid's sanitiser the DOM it expects).
// Prints "OK <diagram type> <number of nodes>" or "ERROR <the reason>", and exits 0 / 1. The node count is 0 when the diagram type has no node list.
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
try { globalThis.navigator = dom.window.navigator; } catch { /* newer Node defines a read-only navigator */ }

const chunks = [];
for await (const c of process.stdin) chunks.push(c);
const code = Buffer.concat(chunks).toString("utf8");

const size = (m) => (m && typeof m.size === "number" ? m.size : Array.isArray(m) ? m.length : Object.keys(m || {}).length);
const countNodes = (diagram) => {
  try {
    const db = diagram.db;
    if (db.getVertices) return size(db.getVertices());
    if (db.getStates) return size(db.getStates());
    if (db.getActors) return size(db.getActors());
    if (db.getMindmap) {
      const walk = (n) => 1 + (n.children || []).reduce((a, c) => a + walk(c), 0);
      const root = db.getMindmap();
      return root ? walk(root) : 0;
    }
  } catch { /* an unknown shape of the diagram database: no count */ }
  return 0;
};

const mermaid = (await import("mermaid")).default;
try {
  const res = await mermaid.parse(code);                       // validates, and loads the diagram type
  let nodes = 0;
  try { nodes = countNodes(await mermaid.mermaidAPI.getDiagramFromText(code)); } catch { /* no count for this type */ }
  console.log("OK " + (res ? res.diagramType : "?") + " " + nodes);
} catch (e) {
  console.log("ERROR " + String((e && e.message) || e).split("\n").map((x) => x.trim()).filter(Boolean).slice(0, 4).join(" / ").slice(0, 300));
  process.exit(1);
}
