import { useMemo } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import MermaidDiagram from "./MermaidDiagram";

type Part = { kind: "markdown"; text: string } | { kind: "mermaid"; code: string };

const MERMAID_BLOCK = /```mermaid[^\n]*\n([\s\S]*?)```/g;

/** Splits out ```mermaid blocks BEFORE marked runs, so they become real diagrams. */
function splitMermaid(source: string): Part[] {
  const parts: Part[] = [];
  let last = 0;
  for (const match of source.matchAll(MERMAID_BLOCK)) {
    const index = match.index ?? 0;
    if (index > last) parts.push({ kind: "markdown", text: source.slice(last, index) });
    parts.push({ kind: "mermaid", code: match[1] ?? "" });
    last = index + match[0].length;
  }
  if (last < source.length) parts.push({ kind: "markdown", text: source.slice(last) });
  return parts;
}

function toSafeHtml(markdown: string): string {
  const html = marked.parse(markdown, { async: false, gfm: true });
  // The model's output is untrusted: sanitize before it touches the DOM.
  return DOMPurify.sanitize(html);
}

export default function Markdown({ source }: { source: string }) {
  const parts = useMemo(() => splitMermaid(source), [source]);

  return (
    <div className="markdown">
      {parts.map((part, i) =>
        part.kind === "mermaid" ? (
          <MermaidDiagram key={i} code={part.code} />
        ) : (
          <div key={i} dangerouslySetInnerHTML={{ __html: toSafeHtml(part.text) }} />
        ),
      )}
    </div>
  );
}
