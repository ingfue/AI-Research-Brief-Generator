import { useState, useCallback } from "react";
import { Play, Check, Download, Eye, Pencil, ArrowRight } from "lucide-react";
import SessionSelector from "../components/SessionSelector";
import SectionStepper, { type Step, type StepStatus } from "../components/SectionStepper";
import SectionEditor from "../components/SectionEditor";
import ToneAdjuster from "../components/ToneAdjuster";
import DiffViewer from "../components/DiffViewer";
import {
  generateStep,
  updateSection,
  assembleDocument,
  getDownloadUrl,
} from "../services/api";

const SECTIONS = [
  { key: "metadata", label: "Header Metadata" },
  { key: "client_brand", label: "Client & Brand" },
  { key: "project_overview", label: "Project Overview / Background" },
  { key: "objectives", label: "Objectives" },
  { key: "research_questions", label: "Research Questions" },
  { key: "data_timeframe", label: "Data Analysis Timeframe" },
  { key: "research_usage", label: "How Research Will Be Used" },
  { key: "deliverables", label: "Deliverables" },
  { key: "timeline", label: "Project Timeline" },
  { key: "key_assumptions", label: "Key Assumptions" },
  { key: "additional_info", label: "Additional Information" },
];

type ViewMode = "preview" | "edit" | "diff";

export default function HumanReviewPage() {
  const [sessionId, setSessionId] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [steps, setSteps] = useState<Step[]>(
    SECTIONS.map((s) => ({ ...s, status: "pending" as StepStatus }))
  );
  const [contents, setContents] = useState<Record<string, string>>({});
  const [originalContents, setOriginalContents] = useState<Record<string, string>>({});
  const [viewMode, setViewMode] = useState<ViewMode>("preview");
  const [error, setError] = useState<string | null>(null);
  const [assembling, setAssembling] = useState(false);
  const [docUrl, setDocUrl] = useState<string | null>(null);

  const currentStep = SECTIONS[activeIndex];
  const currentContent = contents[currentStep.key] || "";
  const currentOriginal = originalContents[currentStep.key] || "";
  const allApproved = steps.every((s) => s.status === "approved");

  const updateStepStatus = useCallback((index: number, status: StepStatus) => {
    setSteps((prev) => prev.map((s, i) => (i === index ? { ...s, status } : s)));
  }, []);

  const handleGenerate = async () => {
    if (!sessionId) return;
    setError(null);
    updateStepStatus(activeIndex, "generating");

    try {
      const result = await generateStep(sessionId, currentStep.key);
      setContents((prev) => ({ ...prev, [currentStep.key]: result.content }));
      setOriginalContents((prev) => ({ ...prev, [currentStep.key]: result.content }));
      updateStepStatus(activeIndex, "review");
      setViewMode("preview");
    } catch (err: any) {
      updateStepStatus(activeIndex, "pending");
      setError(err.response?.data?.detail || "Generation failed");
    }
  };

  const handleApprove = async () => {
    try {
      await updateSection(sessionId, currentStep.key, currentContent, "approved");
      updateStepStatus(activeIndex, "approved");
      if (activeIndex < SECTIONS.length - 1) {
        setActiveIndex(activeIndex + 1);
        setViewMode("preview");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to save section");
    }
  };

  const handleAssemble = async () => {
    setAssembling(true);
    setError(null);
    try {
      await assembleDocument(sessionId);
      setDocUrl(getDownloadUrl(sessionId));
    } catch (err: any) {
      setError(err.response?.data?.detail || "Assembly failed");
    } finally {
      setAssembling(false);
    }
  };

  const handleToneApply = (adjusted: string) => {
    setContents((prev) => ({ ...prev, [currentStep.key]: adjusted }));
    setViewMode("diff");
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", paddingTop: 32 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Human Review</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24 }}>
        Generate each section, review and edit the content, then approve before moving to the next step.
      </p>

      <SessionSelector value={sessionId} onChange={(id) => { setSessionId(id); setDocUrl(null); }} />

      {!sessionId ? (
        <div
          style={{
            padding: 40,
            textAlign: "center",
            color: "var(--text-muted)",
            background: "var(--bg-card)",
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--border)",
          }}
        >
          Select a session above to begin the review process.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 20 }}>
          {/* Left: Stepper */}
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              padding: 12,
              height: "fit-content",
              position: "sticky",
              top: 20,
            }}
          >
            <SectionStepper
              steps={steps}
              activeIndex={activeIndex}
              onStepClick={setActiveIndex}
            />
          </div>

          {/* Right: Content area */}
          <div>
            {/* Section header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 16,
              }}
            >
              <h2 style={{ fontSize: 18, fontWeight: 600 }}>{currentStep.label}</h2>
              <div style={{ display: "flex", gap: 6 }}>
                {currentContent && (
                  <>
                    <TabButton active={viewMode === "preview"} onClick={() => setViewMode("preview")}>
                      <Eye size={14} /> Preview
                    </TabButton>
                    <TabButton active={viewMode === "edit"} onClick={() => setViewMode("edit")}>
                      <Pencil size={14} /> Edit
                    </TabButton>
                    {currentOriginal !== currentContent && (
                      <TabButton active={viewMode === "diff"} onClick={() => setViewMode("diff")}>
                        Diff
                      </TabButton>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Error */}
            {error && (
              <div
                style={{
                  padding: 12,
                  background: "var(--error-bg)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: "var(--radius)",
                  marginBottom: 12,
                  fontSize: 13,
                  color: "var(--error)",
                }}
              >
                {error}
              </div>
            )}

            {/* Content area */}
            {steps[activeIndex].status === "pending" ? (
              <div
                style={{
                  padding: 40,
                  textAlign: "center",
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)",
                }}
              >
                <p style={{ color: "var(--text-muted)", marginBottom: 16 }}>
                  This section has not been generated yet.
                </p>
                <button
                  onClick={handleGenerate}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "10px 20px",
                    background: "var(--accent)",
                    color: "#fff",
                    border: "none",
                    borderRadius: "var(--radius)",
                    fontSize: 14,
                    fontWeight: 600,
                  }}
                >
                  <Play size={16} /> Generate This Section
                </button>
              </div>
            ) : steps[activeIndex].status === "generating" ? (
              <div
                style={{
                  padding: 40,
                  textAlign: "center",
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)",
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    border: "3px solid var(--border)",
                    borderTopColor: "var(--accent)",
                    borderRadius: "50%",
                    animation: "spin 0.8s linear infinite",
                    margin: "0 auto 12px",
                  }}
                />
                <p style={{ color: "var(--text-secondary)" }}>Generating content...</p>
              </div>
            ) : (
              <>
                {/* Preview / Edit / Diff */}
                {viewMode === "preview" && (
                  <div
                    style={{
                      padding: 20,
                      background: "var(--bg-card)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-lg)",
                      fontSize: 14,
                      lineHeight: 1.7,
                      color: "var(--text-secondary)",
                      whiteSpace: "pre-wrap",
                      minHeight: 200,
                    }}
                  >
                    {currentContent}
                  </div>
                )}
                {viewMode === "edit" && (
                  <SectionEditor
                    value={currentContent}
                    onChange={(val) =>
                      setContents((prev) => ({ ...prev, [currentStep.key]: val }))
                    }
                  />
                )}
                {viewMode === "diff" && (
                  <DiffViewer original={currentOriginal} modified={currentContent} />
                )}

                {/* Tone Adjuster */}
                <div style={{ marginTop: 16 }}>
                  <ToneAdjuster text={currentContent} onApply={handleToneApply} />
                </div>

                {/* Action buttons */}
                <div
                  style={{
                    display: "flex",
                    gap: 10,
                    marginTop: 16,
                    justifyContent: "flex-end",
                  }}
                >
                  {steps[activeIndex].status !== "approved" && (
                    <button
                      onClick={handleGenerate}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "8px 16px",
                        background: "transparent",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius)",
                        color: "var(--text-secondary)",
                        fontSize: 13,
                        fontWeight: 500,
                      }}
                    >
                      Regenerate
                    </button>
                  )}
                  <button
                    onClick={handleApprove}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "8px 20px",
                      background: "var(--success)",
                      color: "#fff",
                      border: "none",
                      borderRadius: "var(--radius)",
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    <Check size={14} />
                    {activeIndex < SECTIONS.length - 1 ? "Approve & Next" : "Approve"}
                    {activeIndex < SECTIONS.length - 1 && <ArrowRight size={14} />}
                  </button>
                </div>
              </>
            )}

            {/* Final assembly */}
            {allApproved && (
              <div
                style={{
                  marginTop: 24,
                  padding: 20,
                  background: "var(--success-bg)",
                  border: "1px solid rgba(34, 197, 94, 0.3)",
                  borderRadius: "var(--radius-lg)",
                  textAlign: "center",
                }}
              >
                <p style={{ fontWeight: 600, color: "var(--success)", marginBottom: 12 }}>
                  All sections approved! Ready to assemble the document.
                </p>
                {docUrl ? (
                  <a
                    href={docUrl}
                    download
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "10px 24px",
                      background: "var(--success)",
                      color: "#fff",
                      borderRadius: "var(--radius)",
                      fontSize: 14,
                      fontWeight: 600,
                    }}
                  >
                    <Download size={16} /> Download Word Document
                  </a>
                ) : (
                  <button
                    onClick={handleAssemble}
                    disabled={assembling}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "10px 24px",
                      background: "var(--accent)",
                      color: "#fff",
                      border: "none",
                      borderRadius: "var(--radius)",
                      fontSize: 14,
                      fontWeight: 600,
                      opacity: assembling ? 0.5 : 1,
                    }}
                  >
                    {assembling ? "Assembling..." : "Assemble Document"}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "6px 10px",
        fontSize: 12,
        fontWeight: 500,
        border: "1px solid",
        borderColor: active ? "var(--accent)" : "var(--border)",
        background: active ? "rgba(99, 102, 241, 0.1)" : "transparent",
        color: active ? "var(--accent)" : "var(--text-secondary)",
        borderRadius: "var(--radius)",
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      {children}
    </button>
  );
}
