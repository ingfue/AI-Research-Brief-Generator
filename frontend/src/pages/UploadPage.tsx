import { useState, useCallback } from "react";
import { Upload, CheckCircle, AlertCircle, FileJson } from "lucide-react";
import { uploadJson, type UploadResponse } from "../services/api";

export default function UploadPage() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    setResult(null);

    if (!file.name.endsWith(".json")) {
      setError("Please upload a .json file");
      return;
    }

    // Validate JSON
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      if (!data.deal && !data.activities) {
        setError("JSON must contain 'deal' and/or 'activities' keys");
        return;
      }
    } catch {
      setError("Invalid JSON file");
      return;
    }

    setUploading(true);
    try {
      const res = await uploadJson(file);
      setResult(res);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", paddingTop: 32 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Upload HubSpot Data</h1>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24 }}>
        Upload a JSON file exported from HubSpot containing deal and conversation data.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{
          border: `2px dashed ${dragging ? "var(--accent)" : "var(--border)"}`,
          borderRadius: "var(--radius-lg)",
          padding: 48,
          textAlign: "center",
          background: dragging ? "rgba(99, 102, 241, 0.05)" : "var(--bg-card)",
          transition: "all 0.2s",
          cursor: "pointer",
        }}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".json"
          onChange={onFileInput}
          style={{ display: "none" }}
        />
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: "50%",
            background: "rgba(99, 102, 241, 0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 16px",
          }}
        >
          {uploading ? (
            <div
              style={{
                width: 24,
                height: 24,
                border: "3px solid var(--border)",
                borderTopColor: "var(--accent)",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
              }}
            />
          ) : (
            <Upload size={24} color="var(--accent)" />
          )}
        </div>
        <p style={{ fontWeight: 600, marginBottom: 4 }}>
          {uploading ? "Uploading & indexing..." : "Drop your JSON file here"}
        </p>
        <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
          or click to browse
        </p>
      </div>

      {/* Result */}
      {result && (
        <div
          style={{
            marginTop: 20,
            padding: 20,
            background: "var(--success-bg)",
            border: "1px solid rgba(34, 197, 94, 0.3)",
            borderRadius: "var(--radius-lg)",
            display: "flex",
            gap: 12,
          }}
        >
          <CheckCircle size={20} color="var(--success)" style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <p style={{ fontWeight: 600, color: "var(--success)", marginBottom: 8 }}>Upload Successful</p>
            <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px", fontSize: 14 }}>
              <span style={{ color: "var(--text-muted)" }}>Session ID:</span>
              <code style={{ background: "var(--bg-input)", padding: "2px 6px", borderRadius: 4 }}>
                {result.session_id}
              </code>
              <span style={{ color: "var(--text-muted)" }}>File:</span>
              <span>{result.filename}</span>
              <span style={{ color: "var(--text-muted)" }}>Chunks indexed:</span>
              <span>{result.chunk_count}</span>
            </div>
            <p style={{ marginTop: 12, fontSize: 13, color: "var(--text-secondary)" }}>
              You can now go to <strong>Full Generate</strong> or <strong>Human Review</strong> to create the proposal document.
            </p>
          </div>
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
            display: "flex",
            gap: 12,
            alignItems: "center",
          }}
        >
          <AlertCircle size={20} color="var(--error)" />
          <p style={{ color: "var(--error)" }}>{error}</p>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
