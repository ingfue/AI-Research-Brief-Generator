import { useState, useEffect, useCallback } from "react";
import {
  Search,
  Database,
  Layers,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  BarChart3,
  Eye,
} from "lucide-react";
import {
  debugListSessions,
  debugGetStats,
  debugGetSectionChunks,
  debugGetAggregate,
  debugSearch,
  type DebugSession,
  type DebugStats,
  type DebugChunk,
  type DebugAggregate,
} from "../services/api";

const AGENT_SECTIONS = [
  { tag: "metadata", label: "Metadata", color: "#9ca3af" },
  { tag: "client_brand", label: "Client & Brand", color: "#3b82f6" },
  { tag: "project_overview", label: "Project Overview", color: "#6366f1" },
  { tag: "objectives", label: "Objectives", color: "#8b5cf6" },
  { tag: "research_questions", label: "Research Questions", color: "#a855f7" },
  { tag: "data_timeframe", label: "Data & Timeframe", color: "#d946ef" },
  { tag: "research_usage", label: "Research Usage", color: "#ec4899" },
  { tag: "deliverables", label: "Deliverables", color: "#f43f5e" },
  { tag: "timeline", label: "Timeline", color: "#f59e0b" },
  { tag: "key_assumptions", label: "Key Assumptions", color: "#22c55e" },
  { tag: "additional_info", label: "Additional Info", color: "#14b8a6" },
];

export default function DebugPage() {
  const [sessions, setSessions] = useState<DebugSession[]>([]);
  const [selectedSession, setSelectedSession] = useState("");
  const [stats, setStats] = useState<DebugStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Per-section expanded state
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [sectionData, setSectionData] = useState<
    Record<string, { aggregate: DebugAggregate | null; chunks: DebugChunk[] }>
  >({});
  const [sectionLoading, setSectionLoading] = useState<Record<string, boolean>>({});

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchTier, setSearchTier] = useState<string>("");
  const [searchTag, setSearchTag] = useState<string>("");
  const [searchResults, setSearchResults] = useState<DebugChunk[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    debugListSessions().then(setSessions).catch(() => {});
  }, []);

  const loadStats = useCallback(async (sid: string) => {
    setLoading(true);
    setError("");
    setStats(null);
    setSectionData({});
    setExpanded({});
    setSearchResults(null);
    try {
      const s = await debugGetStats(sid);
      setStats(s);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load stats");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSessionChange = (sid: string) => {
    setSelectedSession(sid);
    if (sid) loadStats(sid);
  };

  const toggleSection = async (tag: string) => {
    const isOpen = !expanded[tag];
    setExpanded((prev) => ({ ...prev, [tag]: isOpen }));
    if (isOpen && !sectionData[tag]) {
      setSectionLoading((prev) => ({ ...prev, [tag]: true }));
      try {
        const [agg, chunks] = await Promise.all([
          debugGetAggregate(selectedSession, tag),
          debugGetSectionChunks(selectedSession, tag),
        ]);
        setSectionData((prev) => ({
          ...prev,
          [tag]: { aggregate: agg, chunks: chunks.chunks },
        }));
      } catch {
        setSectionData((prev) => ({
          ...prev,
          [tag]: { aggregate: null, chunks: [] },
        }));
      } finally {
        setSectionLoading((prev) => ({ ...prev, [tag]: false }));
      }
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim() || !selectedSession) return;
    setSearching(true);
    try {
      const res = await debugSearch(selectedSession, searchQuery, {
        top: 10,
        chunk_tier: searchTier || undefined,
        section_tag: searchTag || undefined,
      });
      setSearchResults(res.results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.03em", marginBottom: 6 }}>
          Search Index Debug
        </h1>
        <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
          Inspect exactly what each agent receives from Azure AI Search — zero GPT calls.
        </p>
      </div>

      {/* Session picker */}
      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <Database size={18} color="var(--text-secondary)" />
        <select
          value={selectedSession}
          onChange={(e) => handleSessionChange(e.target.value)}
          style={{
            flex: 1,
            maxWidth: 480,
            padding: "10px 14px",
            background: "var(--bg-input)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-primary)",
            fontSize: 14,
          }}
        >
          <option value="">Select a session...</option>
          {sessions.map((s) => (
            <option key={s.session_id} value={s.session_id}>
              {s.session_id} ({s.chunk_count} chunks)
            </option>
          ))}
        </select>
        <button
          onClick={() => debugListSessions().then(setSessions)}
          style={{
            padding: "10px 12px",
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            color: "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
          }}
          title="Refresh sessions"
        >
          <RefreshCw size={16} />
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: "12px 16px",
            background: "var(--error-bg)",
            border: "1px solid var(--error)",
            borderRadius: "var(--radius)",
            color: "var(--error)",
            fontSize: 14,
            marginBottom: 20,
          }}
        >
          {error}
        </div>
      )}

      {loading && <Spinner label="Loading stats..." />}

      {/* Stats overview */}
      {stats && (
        <>
          <StatsPanel stats={stats} />

          {/* Per-agent sections */}
          <div style={{ marginTop: 28, marginBottom: 12 }}>
            <h2
              style={{
                fontSize: 16,
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <Eye size={18} /> Agent Context Viewer
            </h2>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
              Click a section to see the Tier-2 aggregate (primary) and Tier-1 structural chunks
              that the agent retrieves.
            </p>
          </div>

          {AGENT_SECTIONS.map((sec) => {
            const count = stats.by_section_tag[sec.tag] ?? 0;
            const isOpen = expanded[sec.tag];
            const data = sectionData[sec.tag];
            const isLoading = sectionLoading[sec.tag];
            return (
              <div
                key={sec.tag}
                style={{
                  marginBottom: 8,
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  overflow: "hidden",
                }}
              >
                <button
                  onClick={() => toggleSection(sec.tag)}
                  style={{
                    width: "100%",
                    padding: "14px 18px",
                    background: isOpen ? "var(--bg-card)" : "var(--bg-secondary)",
                    border: "none",
                    color: "var(--text-primary)",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    fontSize: 14,
                    fontWeight: 500,
                    textAlign: "left",
                    transition: "background 0.15s",
                  }}
                >
                  {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      background: sec.color,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ flex: 1 }}>{sec.label}</span>
                  <Badge label={sec.tag} />
                  <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
                    {count} chunk{count !== 1 ? "s" : ""}
                  </span>
                </button>

                {isOpen && (
                  <div style={{ padding: 18, background: "var(--bg-primary)" }}>
                    {isLoading ? (
                      <Spinner label="Loading section..." />
                    ) : data ? (
                      <SectionDetail data={data} tag={sec.tag} />
                    ) : (
                      <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No data loaded.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Free-text search */}
          <div style={{ marginTop: 32, marginBottom: 12 }}>
            <h2
              style={{
                fontSize: 16,
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <Search size={18} /> Search Index
            </h2>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
              Run the same query an agent would, with optional tier/tag filters.
            </p>
          </div>

          <div
            style={{
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              marginBottom: 16,
            }}
          >
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search query (e.g. silk, oat milk, display)..."
              style={{
                flex: 1,
                minWidth: 220,
                padding: "10px 14px",
                background: "var(--bg-input)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                color: "var(--text-primary)",
                fontSize: 14,
              }}
            />
            <select
              value={searchTier}
              onChange={(e) => setSearchTier(e.target.value)}
              style={{
                padding: "10px 12px",
                background: "var(--bg-input)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                color: "var(--text-primary)",
                fontSize: 13,
              }}
            >
              <option value="">Any tier</option>
              <option value="structural">Tier 1 (structural)</option>
              <option value="section_aggregate">Tier 2 (aggregate)</option>
            </select>
            <select
              value={searchTag}
              onChange={(e) => setSearchTag(e.target.value)}
              style={{
                padding: "10px 12px",
                background: "var(--bg-input)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                color: "var(--text-primary)",
                fontSize: 13,
              }}
            >
              <option value="">Any section</option>
              {AGENT_SECTIONS.map((s) => (
                <option key={s.tag} value={s.tag}>
                  {s.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleSearch}
              disabled={searching || !searchQuery.trim()}
              style={{
                padding: "10px 20px",
                background: "var(--accent)",
                border: "none",
                borderRadius: "var(--radius)",
                color: "#fff",
                fontWeight: 600,
                fontSize: 14,
                opacity: searching || !searchQuery.trim() ? 0.5 : 1,
              }}
            >
              {searching ? "Searching..." : "Search"}
            </button>
          </div>

          {searchResults !== null && (
            <div style={{ marginBottom: 32 }}>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 10 }}>
                {searchResults.length} result{searchResults.length !== 1 ? "s" : ""}
              </p>
              {searchResults.length === 0 ? (
                <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
                  No matches. Try a broader query.
                </p>
              ) : (
                searchResults.map((c) => <ChunkCard key={c.chunk_id} chunk={c} />)
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function StatsPanel({ stats }: { stats: DebugStats }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: 14,
      }}
    >
      <StatCard label="Total Chunks" value={stats.total_chunks} icon={<Layers size={18} />} />
      {Object.entries(stats.by_tier).map(([tier, count]) => (
        <StatCard
          key={tier}
          label={tier === "structural" ? "Tier 1 (Structural)" : "Tier 2 (Aggregates)"}
          value={count}
          icon={<BarChart3 size={18} />}
          accent={tier === "structural" ? "var(--info)" : "var(--accent)"}
        />
      ))}
      <StatCard
        label="Section Tags"
        value={Object.keys(stats.by_section_tag).length}
        icon={<Database size={18} />}
        accent="var(--success)"
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  accent?: string;
}) {
  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "18px 20px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 8,
          color: accent ?? "var(--text-secondary)",
        }}
      >
        {icon}
        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function SectionDetail({
  data,
  tag,
}: {
  data: { aggregate: DebugAggregate | null; chunks: DebugChunk[] };
  tag: string;
}) {
  const [showFull, setShowFull] = useState(false);

  return (
    <div>
      {/* Tier-2 aggregate */}
      <div style={{ marginBottom: 16 }}>
        <h4
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--accent)",
            marginBottom: 8,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Tier 2 — Section Aggregate (Primary)
        </h4>
        {data.aggregate?.found ? (
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: 16,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 10,
              }}
            >
              <code style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {data.aggregate.chunk_id}
              </code>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {data.aggregate.content_length} chars
              </span>
            </div>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                fontSize: 13,
                lineHeight: 1.6,
                color: "var(--text-primary)",
                maxHeight: showFull ? "none" : 300,
                overflow: "hidden",
                position: "relative",
              }}
            >
              {data.aggregate.content}
            </pre>
            {(data.aggregate.content_length ?? 0) > 500 && (
              <button
                onClick={() => setShowFull(!showFull)}
                style={{
                  marginTop: 8,
                  fontSize: 13,
                  color: "var(--accent)",
                  background: "none",
                  border: "none",
                  fontWeight: 500,
                }}
              >
                {showFull ? "Show less" : "Show full content"}
              </button>
            )}
          </div>
        ) : (
          <p style={{ color: "var(--warning)", fontSize: 13 }}>
            No aggregate found for <code>{tag}</code>. Agents will fall back to Tier-1 chunks.
          </p>
        )}
      </div>

      {/* Tier-1 structural chunks */}
      <h4
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: "var(--info)",
          marginBottom: 8,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Tier 1 — Structural Chunks ({data.chunks.length})
      </h4>
      {data.chunks.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No Tier-1 chunks for this section.</p>
      ) : (
        data.chunks.map((c) => <ChunkCard key={c.chunk_id} chunk={c} />)
      )}
    </div>
  );
}

function ChunkCard({ chunk }: { chunk: DebugChunk }) {
  const [open, setOpen] = useState(false);

  return (
    <div
      style={{
        background: "var(--bg-secondary)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "12px 16px",
        marginBottom: 8,
      }}
    >
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          cursor: "pointer",
        }}
      >
        {open ? (
          <ChevronDown size={14} color="var(--text-muted)" />
        ) : (
          <ChevronRight size={14} color="var(--text-muted)" />
        )}
        <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>
          {chunk.subject || chunk.chunk_id}
        </span>
        <Badge label={chunk.chunk_tier} />
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
          {chunk.content_length} chars
        </span>
      </div>

      {open && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
            <Badge label={chunk.chunk_type} variant="type" />
            {chunk.section_tags.map((t) => (
              <Badge key={t} label={t} variant="tag" />
            ))}
          </div>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: 13,
              lineHeight: 1.6,
              color: "var(--text-primary)",
              background: "var(--bg-input)",
              borderRadius: "var(--radius)",
              padding: 12,
              maxHeight: 400,
              overflow: "auto",
            }}
          >
            {chunk.content}
          </pre>
          <code style={{ display: "block", marginTop: 6, fontSize: 11, color: "var(--text-muted)" }}>
            ID: {chunk.chunk_id}
            {chunk.parent_chunk_id ? ` | Parent: ${chunk.parent_chunk_id}` : ""}
            {chunk.paragraph_index ? ` | Para: ${chunk.paragraph_index}` : ""}
          </code>
        </div>
      )}
    </div>
  );
}

function Badge({ label, variant }: { label: string; variant?: "type" | "tag" }) {
  const bg =
    variant === "type"
      ? "var(--info-bg)"
      : variant === "tag"
        ? "var(--success-bg)"
        : "rgba(99,102,241,0.12)";
  const color =
    variant === "type" ? "var(--info)" : variant === "tag" ? "var(--success)" : "var(--accent)";
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 4,
        background: bg,
        color,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

function Spinner({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: 12 }}>
      <RefreshCw
        size={16}
        color="var(--accent)"
        style={{ animation: "spin 1s linear infinite" }}
      />
      <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>{label}</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
