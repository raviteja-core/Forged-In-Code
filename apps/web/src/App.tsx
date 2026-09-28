import React from "react";

export const App: React.FC = () => {
  return (
    <div style={{ padding: "2rem", maxWidth: "1200px", margin: "0 auto" }}>
      <header style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1rem", marginBottom: "2rem" }}>
        <h1 style={{ color: "var(--accent-cyan)", margin: 0, fontSize: "1.8rem" }}>ForgeRun</h1>
        <p style={{ color: "var(--text-muted)", marginTop: "0.5rem" }}>
          Distributed Online Judge & Sandboxed Code Execution Engine
        </p>
      </header>
      <main>
        <div style={{ backgroundColor: "var(--bg-secondary)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "1.5rem" }}>
          <h2>System Status</h2>
          <p>Phase 0 Foundation Initialized. Ready for Phase 1 Vertical Slice.</p>
        </div>
      </main>
    </div>
  );
};
