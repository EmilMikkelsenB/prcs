import React, { useState } from "react";
import { api } from "../api.js";

export default function RunnerSetup({ suggested, onSaved }) {
  const [url, setUrl] = useState(suggested || "http://172.28.0.10:8089");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api("/config", { runner_url: url });
      onSaved(url);
    } catch (e2) {
      setErr(e2.message);
    }
    setBusy(false);
  };

  return (
    <div className="login-wrap"><div className="login-box panel"><div className="panel-b">
      <h3>Where is the runner?</h3>
      <p className="muted small">
        One-time setup: tell the host where the runner (the container/host
        running `claude`) is reachable. On a standard `docker compose up` it
        gets the static IP below; change it if yours runs elsewhere.
      </p>
      <form onSubmit={submit}>
        <div className="field">
          <label>Runner URL</label>
          <input value={url} onChange={(e) => setUrl(e.target.value)} autoFocus
                 placeholder="http://172.28.0.10:8089" />
        </div>
        {err && <p className="err">{err}</p>}
        <button className="btn primary" disabled={busy} type="submit">{busy ? "…" : "Save"}</button>
      </form>
    </div></div></div>
  );
}
