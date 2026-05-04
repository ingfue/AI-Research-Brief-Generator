import { useState } from "react";
import { Wand2, Loader } from "lucide-react";
import { adjustTone } from "../services/api";

const PRESETS = [
  { value: "professional", label: "Professional" },
  { value: "concise", label: "Concise" },
  { value: "persuasive", label: "Persuasive" },
  { value: "leadership-ready", label: "Leadership-ready" },
  { value: "friendly", label: "Friendly" },
  { value: "custom", label: "Custom..." },
];

interface Props {
  text: string;
  onApply: (adjusted: string) => void;
}

export default function ToneAdjuster({ text, onApply }: Props) {
  const [tone, setTone] = useState("professional");
  const [customInstruction, setCustomInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const handleAdjust = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setPreview(null);
    try {
      const result = await adjustTone(
        text,
        tone === "custom" ? "custom" : tone,
        tone === "custom" ? customInstruction : undefined
      );
      setPreview(result.adjusted);
    } catch {
      // Silently fail for POC
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: 16,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <Wand2 size={16} color="var(--accent)" />
        <span style={{ fontSize: 13, fontWeight: 600 }}>AI Tone Adjuster</span>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        {PRESETS.map((p) => (
          <button
            key={p.value}
            onClick={() => setTone(p.value)}
            style={{
              padding: "6px 12px",
              fontSize: 12,
              fontWeight: 500,
              border: "1px solid",
              borderColor: tone === p.value ? "var(--accent)" : "var(--border)",
              background: tone === p.value ? "rgba(99, 102, 241, 0.1)" : "transparent",
              color: tone === p.value ? "var(--accent)" : "var(--text-secondary)",
              borderRadius: 20,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {tone === "custom" && (
        <input
          value={customInstruction}
          onChange={(e) => setCustomInstruction(e.target.value)}
          placeholder="e.g. 'Make it more data-driven and strategic'"
          style={{
            width: "100%",
            padding: "8px 12px",
            background: "var(--bg-input)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-primary)",
            fontSize: 13,
            marginBottom: 12,
            outline: "none",
          }}
        />
      )}

      <button
        onClick={handleAdjust}
        disabled={loading || !text.trim()}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "8px 16px",
          background: "var(--accent)",
          color: "#fff",
          border: "none",
          borderRadius: "var(--radius)",
          fontSize: 13,
          fontWeight: 600,
          opacity: loading || !text.trim() ? 0.5 : 1,
          cursor: loading ? "wait" : "pointer",
        }}
      >
        {loading ? <Loader size={14} style={{ animation: "spin 0.8s linear infinite" }} /> : <Wand2 size={14} />}
        {loading ? "Adjusting..." : "Adjust Tone"}
      </button>

      {preview && (
        <div style={{ marginTop: 16 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 8,
            }}
          >
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)" }}>
              PREVIEW
            </span>
            <button
              onClick={() => { onApply(preview); setPreview(null); }}
              style={{
                padding: "4px 12px",
                background: "var(--success)",
                color: "#fff",
                border: "none",
                borderRadius: "var(--radius)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Accept Changes
            </button>
          </div>
          <div
            style={{
              padding: 12,
              background: "var(--bg-input)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              lineHeight: 1.7,
              color: "var(--text-secondary)",
              whiteSpace: "pre-wrap",
              maxHeight: 200,
              overflowY: "auto",
            }}
          >
            {preview}
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
