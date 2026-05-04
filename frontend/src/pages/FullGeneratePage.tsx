import { useState } from "react";
import { Zap, Download, Loader, CheckCircle } from "lucide-react";
import SessionSelector from "../components/SessionSelector";
import { generateFull, getDownloadUrl, type SectionContent } from "../services/api";

const SECTION_LABELS: Record<string, string> = {
  metadata: "Header Metadata",
  client_brand: "Client & Brand",
  project_overview: "Project Overview / Background",
  objectives: "Objectives",
  research_questions: "Research Questions",
  data_timeframe: "Data Analysis Timeframe",
  research_usage: "How Research Will Be Used",
  deliverables: "Deliverables",
  timeline: "Project Timeline",
  key_assumptions: "Key Assumptions",
  additional_info: "Additional Information",
};

export default function FullGeneratePage() {
  const [sessionId, setSessionId] = useState("");
  const [generating, setGenerating] = useState(false);
  const [sections, setSections] = useState<SectionContent[]>([]);
  const [docUrl, setDocUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentSection, setCurrentSection] = useState("");

  const handleGenerate = async () => {
    if (!sessionId) return;
    setError(null);
    setSections([]);
    setDocUrl(null);
    setGenerating(true);
    setCurrentSection("Starting generation...");

    try {
      const result = await generateFull(sessionId);
      setSections(result.sections);
      setDocUrl(getDownloadUrl(sessionId));
      setCurrentSection("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", paddingTop: 32 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Full Generate</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24 }}>
        Generate the complete research brief in one click. All 6 agents will run sequentially.
      </p>

      <SessionSelector value={sessionId} onChange={setSessionId} />

      <button
        onClick={handleGenerate}
        disabled={!sessionId || generating}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 20px",
          background: generating ? "var(--bg-hover)" : "var(--accent)",
          color: "#fff",
          border: "none",
          borderRadius: "var(--radius)",
          fontSize: 14,
          fontWeight: 600,
          opacity: !sessionId ? 0.5 : 1,
          transition: "all 0.15s",
        }}
      >
        {generating ? <Loader size={16} className="spin" /> : <Zap size={16} />}
        {generating ? "Generating..." : "Generate Full Document"}
      </button>

      {/* Progress */}
      {generating && (
        <div
          style={{
            marginTop: 20,
            padding: 16,
            background: "var(--info-bg)",
            border: "1px solid rgba(59, 130, 246, 0.3)",
            borderRadius: "var(--radius-lg)",
            fontSize: 14,
          }}
        >
          <p style={{ color: "var(--info)" }}>{currentSection}</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          style={{
            marginTop: 20,
            padding: 16,
            background: "var(--error-bg)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "var(--radius-lg)",
          }}
        >
          <p style={{ color: "var(--error)" }}>{error}</p>
        </div>
      )}

      {/* Results */}
      {sections.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 16,
            }}
          >
            <h2 style={{ fontSize: 18, fontWeight: 600 }}>Generated Sections</h2>
            {docUrl && (
              <a
                href={docUrl}
                download
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 20px",
                  background: "var(--success)",
                  color: "#fff",
                  borderRadius: "var(--radius)",
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                <Download size={16} /> Download Word Document
              </a>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {sections.map((s) => (
              <details
                key={s.section}
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  overflow: "hidden",
                }}
              >
                <summary
                  style={{
                    padding: "12px 16px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontWeight: 600,
                    fontSize: 14,
                  }}
                >
                  <CheckCircle size={16} color="var(--success)" />
                  {SECTION_LABELS[s.section] || s.section}
                </summary>
                <div
                  style={{
                    padding: "0 16px 16px",
                    fontSize: 14,
                    color: "var(--text-secondary)",
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.7,
                  }}
                >
                  {s.content}
                </div>
              </details>
            ))}
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; }
      `}</style>
    </div>
  );
}
