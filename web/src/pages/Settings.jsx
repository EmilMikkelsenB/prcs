import React, { useEffect, useState } from "react";
import { api, useFetch } from "../api.js";
import { Card, Button, Chip, Field, useToast } from "../ui.jsx";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function ClaudeAccess() {
  const toast = useToast();
  const [runner, reload] = useFetch("/runner", 15000);
  const [kind, setKind] = useState("oauth_token");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const rn = runner?.runner;
  const act = async (body, msg) => {
    setBusy(true);
    try { await api("/claude-auth", body); setValue(""); toast(msg); reload(); } catch (e) { toast(e.message, "bad"); }
    setBusy(false);
  };
  const src = { oauth_token: "subscription token", api_key: "API key", login: "interactive login" }[rn?.source];
  return (
    <Card title="Claude access" aside={<Chip tone={!rn?.ok ? "bad" : rn.logged_in ? "ok" : "warn"}>
      {!rn?.ok ? "runner unreachable" : rn.logged_in ? `signed in (${src})` : "not signed in"}</Chip>}>
      <p className="muted small">The runner needs credentials to run Claude. On any computer where you're signed in to Claude, run{" "}
        <code>claude setup-token</code> and paste the token here, or paste an Anthropic API key. It's stored on the runner only and never shown again.</p>
      <div className="row">
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Credential type">
          <option value="oauth_token">Subscription token (claude setup-token)</option>
          <option value="api_key">Anthropic API key</option>
        </select>
        <input className="grow" type="password" autoComplete="off" value={value} placeholder={kind === "api_key" ? "sk-ant-api…" : "sk-ant-oat…"}
               onChange={(e) => setValue(e.target.value)} />
        <Button kind="primary" busy={busy} disabled={!value} onClick={() => act({ kind, value }, "Claude credentials saved")}>Save</Button>
        {rn?.logged_in && rn.source !== "login" && <Button kind="danger" busy={busy} onClick={() => act({ clear: true }, "Credentials removed")}>Remove</Button>}
      </div>
    </Card>
  );
}

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
      <ClaudeAccess />
      <form onSubmit={save}>
        <Card title="Live settings" aside={<span className="muted small">apply immediately</span>}>
          {data.runtime.map((s) => (
            <Field key={s.key} label={s.label}>
              {s.options ? (
                <select value={vals.runtime[s.key] ?? ""} onChange={(e) => set("runtime", s.key, e.target.value)}>
                  {s.options.map((o) => <option key={o}>{o}</option>)}
                </select>
              ) : (
                <input type={s.type === "int" ? "number" : "text"} min={s.min ?? undefined} max={s.max ?? undefined}
                       value={vals.runtime[s.key] ?? ""} onChange={(e) => set("runtime", s.key, e.target.value)} />
              )}
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
