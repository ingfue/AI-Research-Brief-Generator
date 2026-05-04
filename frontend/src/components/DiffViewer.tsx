import { diffLines, type Change } from "diff";

interface Props {
  original: string;
  modified: string;
}

export default function DiffViewer({ original, modified }: Props) {
  if (original === modified) {
    return (
      <p style={{ fontSize: 13, color: "var(--text-muted)", padding: 12 }}>
        No changes detected.
      </p>
    );
  }

  const changes: Change[] = diffLines(original, modified);

  return (
    <div
      style={{
        fontFamily: "monospace",
        fontSize: 12,
        lineHeight: 1.6,
        background: "var(--bg-input)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        overflow: "auto",
        maxHeight: 300,
      }}
    >
      {changes.map((change, i) => {
        let bg = "transparent";
        let color = "var(--text-secondary)";
        let prefix = " ";

        if (change.added) {
          bg = "rgba(34, 197, 94, 0.08)";
          color = "var(--success)";
          prefix = "+";
        } else if (change.removed) {
          bg = "rgba(239, 68, 68, 0.08)";
          color = "var(--error)";
          prefix = "-";
        }

        return (
          <div key={i} style={{ background: bg, padding: "0 12px", whiteSpace: "pre-wrap" }}>
            {change.value.split("\n").filter(Boolean).map((line, j) => (
              <div key={j} style={{ color }}>
                <span style={{ userSelect: "none", opacity: 0.5, marginRight: 8 }}>{prefix}</span>
                {line}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
