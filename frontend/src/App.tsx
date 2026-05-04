import { Routes, Route, Link, useLocation } from "react-router-dom";
import HomePage from "./pages/HomePage";
import UploadPage from "./pages/UploadPage";
import FullGeneratePage from "./pages/FullGeneratePage";
import HumanReviewPage from "./pages/HumanReviewPage";
import DebugPage from "./pages/DebugPage";

function App() {
  const location = useLocation();
  const isHome = location.pathname === "/";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          background: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border)",
          padding: "0 24px",
          height: 56,
          display: "flex",
          alignItems: "center",
          gap: 32,
        }}
      >
        <Link
          to="/"
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: "var(--text-primary)",
            letterSpacing: "-0.02em",
          }}
        >
          Proposal Generator
        </Link>
        {!isHome && (
          <nav style={{ display: "flex", gap: 16 }}>
            <NavLink to="/upload" current={location.pathname}>Upload</NavLink>
            <NavLink to="/generate" current={location.pathname}>Full Generate</NavLink>
            <NavLink to="/review" current={location.pathname}>Human Review</NavLink>
            <NavLink to="/debug" current={location.pathname}>Debug</NavLink>
          </nav>
        )}
      </header>

      <main style={{ flex: 1, padding: 24 }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/generate" element={<FullGeneratePage />} />
          <Route path="/review" element={<HumanReviewPage />} />
          <Route path="/debug" element={<DebugPage />} />
        </Routes>
      </main>
    </div>
  );
}

function NavLink({ to, current, children }: { to: string; current: string; children: React.ReactNode }) {
  const active = current === to;
  return (
    <Link
      to={to}
      style={{
        fontSize: 14,
        fontWeight: 500,
        color: active ? "var(--accent)" : "var(--text-secondary)",
        padding: "6px 12px",
        borderRadius: "var(--radius)",
        background: active ? "rgba(99, 102, 241, 0.1)" : "transparent",
        transition: "all 0.15s",
      }}
    >
      {children}
    </Link>
  );
}

export default App;
