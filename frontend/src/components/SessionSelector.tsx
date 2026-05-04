import { useEffect, useState } from "react";
import { listSessions, type SessionInfo } from "../services/api";
import { Database } from "lucide-react";

interface Props {
  value: string;
  onChange: (sessionId: string) => void;
}

export default function SessionSelector({ value, onChange }: Props) {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ marginBottom: 24 }}>
      <label
        style={{
          display: "block",
          fontSize: 13,
          fontWeight: 600,
          color: "var(--text-secondary)",
          marginBottom: 6,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Select Session
      </label>
      <div style={{ position: "relative" }}>
        <Database
          size={16}
          style={{
            position: "absolute",
            left: 12,
            top: "50%",
            transform: "translateY(-50%)",
            color: "var(--text-muted)",
          }}
        />
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading}
          style={{
            width: "100%",
            padding: "10px 12px 10px 36px",
            background: "var(--bg-input)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-primary)",
            fontSize: 14,
            appearance: "none",
            cursor: "pointer",
          }}
        >
          <option value="">
            {loading ? "Loading sessions..." : "-- Choose an uploaded session --"}
          </option>
          {sessions.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {s.filename} ({s.session_id}) -- {new Date(s.created_at).toLocaleDateString()}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
