import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { Card, Button, Field, useToast } from "../ui.jsx";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export default function Settings() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [vals, setVals] = useState({ runtime: {}, env: {} });
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(null); // {restart_needed, compose_needed} after a save

  const load = () => api("/settings").then((d) => {
    setData(d);
    setVals({
      runtime: Object.fromEntries(d.runtime.map((s) => [s.key, s.value])),
      env: Object.fromEntries(d.env.map((s) => [s.key, s.value])),
    });
  }).catch((e) => toast(e.message, "bad"));
  useEffect(() => { load(); }, []);

  const set = (group, k, v) => setVals((p) => ({ ...p, [group]: { ...p[group], [k]: v } }));

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api("/settings", vals);
      toast("Settings saved");
      setPending(r.restart_needed || r.compose_needed ? r : null);
      await load();
    } catch (err) { toast(err.message, "bad"); }
    setBusy(false);
  };

  const restart = async () => {
    setBusy(true);
    try {
      await api("/restart", {});
      await sleep(1500); // let the old process go down before polling
      for (let i = 0; i < 20; i++) {
        try { await api("/runner"); break; } catch { await sleep(1000); }
      }
      toast("Host restarted");
      setPending((p) => (p?.compose_needed ? { ...p, restart_needed: false } : null));
    } catch (err) { toast(err.message, "bad"); }
    setBusy(false);
  };

  if (!data) return null;
  return (
    <>
      {pending?.restart_needed && (
        <div className="banner" role="alert">
          <p><strong>A restart is needed</strong> for the changed .env values to take effect.
            Restart the host now? You'll be signed back in automatically; running loops on the runner aren't affected.</p>
          <div className="row tight">
            <Button kind="primary" busy={busy} onClick={restart}>Restart now</Button>
            <Button onClick={() => setPending((p) => (p.compose_needed ? { ...p, restart_needed: false } : null))}>Later</Button>
          </div>
        </div>
      )}
      {pending?.compose_needed && (
        <div className="banner" role="alert">
          <p><strong>One more step:</strong> the port / KB folder changes only apply when the stack is recreated.
            Run <code>docker compose up -d</code> on the machine (the dash can't do that for itself).</p>
          <Button onClick={() => setPending(null)}>Got it</Button>
        </div>
      )}
      <form onSubmit={save}>
        <Card title="Live settings" aside={<span className="muted small">apply immediately</span>}>
          {data.runtime.map((s) => (
            <Field key={s.key} label={s.label}>
              <input type={s.type === "int" ? "number" : "text"} min={s.min ?? undefined} max={s.max ?? undefined}
                     value={vals.runtime[s.key] ?? ""} onChange={(e) => set("runtime", s.key, e.target.value)} />
              {s.help && <span className="muted small">{s.help}</span>}
            </Field>
          ))}
        </Card>
        <Card title="Environment (.env)" aside={<span className="muted small">needs a restart</span>}>
          {data.env.map((s) => (
            <Field key={s.key} label={`${s.label}${s.restart === "compose" ? " — recreate stack" : ""}`}>
              <input type={s.secret ? "password" : "text"} value={vals.env[s.key] ?? ""} autoComplete="off"
                     placeholder={s.secret ? (s.set ? "unchanged — type to replace" : "not set") : ""}
                     onChange={(e) => set("env", s.key, e.target.value)} />
              {s.help && <span className="muted small">{s.help}</span>}
            </Field>
          ))}
        </Card>
        <Button kind="primary" busy={busy} type="submit">Save changes</Button>
      </form>
    </>
  );
}
