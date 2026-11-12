import React, { useState } from "react";
import { Icon } from "../ui.jsx";

export default function Login({ onLoggedIn }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await fetch("/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.error) throw new Error(j.error || "login failed");
      onLoggedIn();
    } catch (e2) {
      setErr(e2.message);
    }
    setBusy(false);
  };

  return (
    <div className="login-wrap">
      <div className="login-box panel">
        <div className="panel-b">
          <div className="brand"><span className="mark"><Icon name="loops" size={14} /></span>Wellqon Cadence</div>
          <form onSubmit={submit}>
            <div className="field">
              <label>Username</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
            </div>
            <div className="field">
              <label>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </div>
            {err && <p className="err">{err}</p>}
            <button className="btn primary" disabled={busy} type="submit">{busy ? "…" : "Sign in"}</button>
          </form>
        </div>
      </div>
    </div>
  );
}
