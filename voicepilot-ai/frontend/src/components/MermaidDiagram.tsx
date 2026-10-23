import { useEffect, useState } from "react";

// Mermaid is large, so it's loaded only when the first diagram renders.
type MermaidApi = (typeof import("mermaid"))["default"];
let mermaidPromise: Promise<MermaidApi> | null = null;
let counter = 0;

function loadMermaid(): Promise<MermaidApi> {
  mermaidPromise ??= import("mermaid").then(({ default: mermaid }) => {
    const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: dark ? "dark" : "default",
    });
    return mermaid;
  });
  return mermaidPromise;
}

export default function MermaidDiagram({ code }: { code: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const id = `mermaid-${++counter}`;
    setSvg(null);
    setFailed(false);

    loadMermaid()
      .then((mermaid) => mermaid.render(id, code.trim()))
      .then(({ svg: out }) => {
        if (!cancelled) setSvg(out);
      })
      .catch(() => {
        // Mermaid leaves its error graphic in <body> when rendering fails.
        document.getElementById(`d${id}`)?.remove();
        document.getElementById(id)?.remove();
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [code]);

  if (failed) {
    return (
      <div className="diagram diagram-failed">
        <p className="alert alert-warning">Diagram could not be rendered</p>
        <pre>
          <code>{code}</code>
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="diagram diagram-loading muted small">
        <span className="spinner spinner-xs" aria-hidden="true" /> Rendering diagram…
      </div>
    );
  }

  // securityLevel "strict" makes Mermaid sanitize labels and drop scripts.
  return <div className="diagram" dangerouslySetInnerHTML={{ __html: svg }} />;
}
