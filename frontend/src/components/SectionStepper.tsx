import { CheckCircle, Circle, Loader, Pencil } from "lucide-react";

export type StepStatus = "pending" | "generating" | "review" | "approved";

export interface Step {
  key: string;
  label: string;
  status: StepStatus;
}

interface Props {
  steps: Step[];
  activeIndex: number;
  onStepClick: (index: number) => void;
}

const STATUS_CONFIG: Record<StepStatus, { icon: typeof Circle; color: string }> = {
  pending: { icon: Circle, color: "var(--text-muted)" },
  generating: { icon: Loader, color: "var(--warning)" },
  review: { icon: Pencil, color: "var(--info)" },
  approved: { icon: CheckCircle, color: "var(--success)" },
};

export default function SectionStepper({ steps, activeIndex, onStepClick }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {steps.map((step, i) => {
        const { icon: Icon, color } = STATUS_CONFIG[step.status];
        const isActive = i === activeIndex;

        return (
          <button
            key={step.key}
            onClick={() => onStepClick(i)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              background: isActive ? "var(--bg-hover)" : "transparent",
              border: "1px solid",
              borderColor: isActive ? "var(--border-focus)" : "transparent",
              borderRadius: "var(--radius)",
              cursor: "pointer",
              color: "var(--text-primary)",
              textAlign: "left",
              transition: "all 0.15s",
            }}
          >
            <Icon
              size={18}
              color={color}
              style={step.status === "generating" ? { animation: "spin 0.8s linear infinite" } : {}}
            />
            <div>
              <div style={{ fontSize: 13, fontWeight: isActive ? 600 : 500 }}>
                {step.label}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color,
                  textTransform: "capitalize",
                  marginTop: 1,
                }}
              >
                {step.status}
              </div>
            </div>
          </button>
        );
      })}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
