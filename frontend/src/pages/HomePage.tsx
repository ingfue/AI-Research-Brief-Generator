import { useNavigate } from "react-router-dom";
import { Upload, Zap, UserCheck, Bug } from "lucide-react";

const cards = [
  {
    title: "Upload JSON",
    description: "Upload HubSpot deal data to get started. The JSON will be stored and indexed for AI processing.",
    icon: Upload,
    path: "/upload",
    color: "#3b82f6",
  },
  {
    title: "Full Generate",
    description: "Generate the complete research brief in one click. All sections are created automatically.",
    icon: Zap,
    path: "/generate",
    color: "#6366f1",
  },
  {
    title: "Human Review",
    description: "Generate section by section with review, editing, and AI tone adjustment at each step.",
    icon: UserCheck,
    path: "/review",
    color: "#22c55e",
  },
  {
    title: "Debug Index",
    description: "Inspect what each agent receives from Azure AI Search — chunks, aggregates, filters, and free-text search.",
    icon: Bug,
    path: "/debug",
    color: "#f59e0b",
  },
];

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", paddingTop: 48 }}>
      <div style={{ textAlign: "center", marginBottom: 48 }}>
        <h1 style={{ fontSize: 32, fontWeight: 700, marginBottom: 12, letterSpacing: "-0.03em" }}>
          Proposal Generator
        </h1>
        <p style={{ fontSize: 16, color: "var(--text-secondary)", maxWidth: 540, margin: "0 auto" }}>
          Transform HubSpot deal data and conversations into professional research brief documents using AI agents.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <button
              key={card.path}
              onClick={() => navigate(card.path)}
              style={{
                background: "var(--bg-card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                padding: 28,
                textAlign: "left",
                transition: "all 0.2s",
                cursor: "pointer",
                color: "inherit",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = card.color;
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = `0 8px 24px ${card.color}22`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "var(--radius)",
                  background: `${card.color}18`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 16,
                }}
              >
                <Icon size={22} color={card.color} />
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>{card.title}</h2>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {card.description}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
