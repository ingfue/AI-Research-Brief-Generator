interface Props {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}

export default function SectionEditor({ value, onChange, readOnly = false }: Props) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      readOnly={readOnly}
      spellCheck
      style={{
        width: "100%",
        minHeight: 280,
        padding: 16,
        background: readOnly ? "var(--bg-secondary)" : "var(--bg-input)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        color: "var(--text-primary)",
        fontSize: 14,
        fontFamily: "inherit",
        lineHeight: 1.7,
        resize: "vertical",
        outline: "none",
        transition: "border-color 0.15s",
      }}
      onFocus={(e) => {
        if (!readOnly) e.currentTarget.style.borderColor = "var(--border-focus)";
      }}
      onBlur={(e) => {
        e.currentTarget.style.borderColor = "var(--border)";
      }}
    />
  );
}
