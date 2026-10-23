import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../services/api";

interface Props {
  mode: "login" | "signup";
}

export default function AuthPage({ mode }: Props) {
  const { login, signup } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isSignup) await signup(username.trim(), email.trim(), password);
      else await login(email.trim(), password);
      // On success the token changes and App swaps to the logged-in routes.
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <h1 className="auth-brand">🎙️ VoicePilot AI</h1>
        <p className="muted">
          {isSignup ? "Create an account to start transcribing lectures." : "Log in to your lectures."}
        </p>

        <form onSubmit={onSubmit} className="form">
          {isSignup && (
            <label className="field">
              <span>Username</span>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </label>
          )}
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSignup ? "new-password" : "current-password"}
              required
            />
          </label>

          {error && (
            <p className="alert alert-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Please wait…" : isSignup ? "Sign up" : "Log in"}
          </button>
        </form>

        <p className="auth-switch">
          {isSignup ? (
            <>
              Already have an account? <Link to="/login">Log in</Link>
            </>
          ) : (
            <>
              New here? <Link to="/signup">Create an account</Link>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
