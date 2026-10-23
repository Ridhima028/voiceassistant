import { useCallback, useEffect, useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { usePolling } from "../hooks/usePolling";
import { api } from "../services/api";

type HealthState = "checking" | "ok" | "db-down" | "unreachable";

const HEALTH_LABEL: Record<HealthState, string> = {
  checking: "Checking…",
  ok: "Backend ok",
  "db-down": "Database down",
  unreachable: "Backend unreachable",
};

export default function AppLayout() {
  const { email, logout } = useAuth();
  const [health, setHealth] = useState<HealthState>("checking");

  const checkHealth = useCallback(() => {
    api
      .health()
      .then((h) => setHealth(h.database ? "ok" : "db-down"))
      .catch(() => setHealth("unreachable"));
  }, []);

  useEffect(checkHealth, [checkHealth]);
  usePolling(checkHealth, 30_000, true);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            🎙️ VoicePilot AI
          </Link>
          <div className="topbar-right">
            <span className={`health-pill health-${health}`} title="GET /health">
              <span className="dot" aria-hidden="true" />
              {HEALTH_LABEL[health]}
            </span>
            {email && <span className="user-email">{email}</span>}
            <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </div>
  );
}
