import React, { useState, useEffect } from "react";
import { api, useFetch, del } from "../api.js";
import { Card, Button, Chip, Empty, Field, Table, useToast } from "../ui.jsx";

const MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-2"];

function LoopForm({ onSaved, tuningKeys, existing }) {
  const toast = useToast();
  const [form, setForm] = useState({ model: "", review: { enabled: false, model: "", prompt: "" }, ...(existing || { name: "", permissions: "files", input: { type: "none" }, output: { queue: "" }, target_repo: "", focus: { text: "" }, tuning: {} }) });
  const [idea, setIdea] = useState("");
  const [tips, setTips] = useState([]);
  const [improving, setImproving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [repos, setRepos] = useState(null);
  const [queueList] = useFetch("/queues", 60000);
  useEffect(() => { api("/github/repos").then(setRepos).catch(() => {}); }, []); // falls back to text input if not connected
  const setReview = (k, v) => setForm((f) => ({ ...f, review: { ...f.review, [k]: v } }));
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setInput = (k, v) => setForm((f) => ({ ...f, input: { ...f.input, [k]: v } }));
  const queueNames = [...new Set([...(queueList || []).filter((q) => q.repo === form.target_repo).map((q) => q.queue), "backlog"])];

  const improve = async () => {
    setImproving(true);
    try {
      const o = await api("/loops/improve", { idea, target_repo: form.target_repo || undefined });
      setForm((f) => ({ ...f, name: f.name || o.name, permissions: o.permissions, focus: { text: o.focus_text },
        input: o.input_queue ? { type: "queue", queue: o.input_queue, auto: f.input?.auto ?? true } : { type: "none" },
        output: { queue: o.output_queue },
        model: o.model || f.model, review: { ...f.review, enabled: o.review_enabled, model: o.review_model || f.review.model } }));
      setTips(o.tips || []);
      toast("Idea improved — review the fields below");
    } catch (err) { toast(err.message, "bad"); }
    setImproving(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const saved = existing?.id ? await api(`/loops/${existing.id}`, form) : await api("/loops", form);
      toast(existing?.id ? "Loop updated" : "Loop created");
      onSaved(saved);
    } catch (err) {
      toast(err.message, "bad");
    }
    setBusy(false);
  };

  return (
    <form onSubmit={submit}>
      <div className="idea-box">
        <Field label="Your idea">
          <textarea rows={3} value={idea} onChange={(e) => setIdea(e.target.value)}
                    placeholder="Describe what this loop should do, in your own words. Rough is fine." />
        </Field>
        <div className="row tight">
          <Button type="button" kind="primary" icon="sparkle" busy={improving} disabled={!idea.trim()} onClick={improve}>Improve</Button>
          <span className="muted small">Claude rewrites it into a full loop prompt and picks permissions, queues, models and review.</span>
        </div>
        {tips.length > 0 && <ul className="tips">{tips.map((t, i) => <li key={i}>{t}</li>)}</ul>}
      </div>
      <Field label="Name"><input value={form.name} onChange={(e) => set("name", e.target.value)} required /></Field>
      <Field label="Target repo (owner/repo)">
        {repos ? (
          <select value={form.target_repo} onChange={(e) => set("target_repo", e.target.value)} required>
            <option value="" disabled>Select a repo…</option>
            {form.target_repo && !repos.some((r) => r.full_name === form.target_repo) && <option>{form.target_repo}</option>}
            {repos.map((r) => <option key={r.full_name} value={r.full_name}>{r.full_name}{r.private ? " (private)" : ""}</option>)}
          </select>
        ) : (
          <input value={form.target_repo} onChange={(e) => set("target_repo", e.target.value)} placeholder="owner/repo (connect GitHub for a list)" required />
        )}
      </Field>
      <Field label="Permissions">
        <select value={form.permissions} onChange={(e) => set("permissions", e.target.value)}>
          <option value="read">Read only — looks at the repo, changes nothing</option>
          <option value="files">Write files — can create files, never commits or pushes</option>
          <option value="push">Full — commits, pushes and opens a pull request</option>
        </select>
      </Field>
      <Field label="Takes its work from">
        <select value={form.input?.type || "none"} onChange={(e) => set("input", e.target.value === "queue" ? { type: "queue", queue: form.input?.queue || "backlog", auto: true } : { type: e.target.value })}>
          <option value="none">Nothing — runs on a schedule or when you start it</option>
          <option value="queue">A queue — takes the oldest item each run</option>
          <option value="previous">The previous step of a flowpath</option>
        </select>
      </Field>
      {form.input?.type === "queue" && (
        <>
          <Field label="Queue to read">
            <input list="queue-names" value={form.input.queue || ""} onChange={(e) => setInput("queue", e.target.value)} required />
          </Field>
          <Field label="Start automatically">
            <label className="check"><input type="checkbox" checked={!!form.input.auto} onChange={(e) => setInput("auto", e.target.checked)} />
              Run as soon as an item arrives (loops inside a flowpath are started by the flowpath)</label>
          </Field>
        </>
      )}
      <Field label="New files go to queue (optional)">
        <input list="queue-names" value={form.output?.queue || ""} onChange={(e) => set("output", { queue: e.target.value })} placeholder="e.g. backlog — leave empty to keep results in the run notes only" />
        <datalist id="queue-names">{queueNames.map((q) => <option key={q} value={q} />)}</datalist>
        <span className="muted small">Each new file this loop creates becomes one item, for another loop to pick up.</span>
      </Field>
      <Field label="Focus / prompt">
        <textarea value={form.focus?.text || ""} onChange={(e) => set("focus", { text: e.target.value })} rows={4} required />
      </Field>
      <Field label="Worker model">
        <input list="models" value={form.model} onChange={(e) => set("model", e.target.value)} placeholder="claude-sonnet-5-5 (default)" />
        <datalist id="models">{MODELS.map((m) => <option key={m} value={m} />)}</datalist>
      </Field>
      <Field label="Review pass">
        <label className="check"><input type="checkbox" checked={!!form.review.enabled} onChange={(e) => setReview("enabled", e.target.checked)} />
          A second model checks the work after each run</label>
      </Field>
      {form.review.enabled && (
        <>
          <Field label="Review model">
            <input list="models" value={form.review.model} onChange={(e) => setReview("model", e.target.value)} placeholder="same as worker" />
          </Field>
          <Field label="Review instructions (optional)">
            <textarea rows={3} value={form.review.prompt} onChange={(e) => setReview("prompt", e.target.value)} placeholder="Leave empty for the default reviewer prompt" />
          </Field>
        </>
      )}
      {Object.entries(tuningKeys || {}).map(([k, v]) => (
        <Field key={k} label={`${v.label} (${v.min}-${v.max})`}>
          <input type="number" min={v.min} max={v.max}
                 value={form.tuning?.[k] ?? v.default}
                 onChange={(e) => set("tuning", { ...form.tuning, [k]: Number(e.target.value) })} />
        </Field>
      ))}
      <Button kind="primary" busy={busy} type="submit">{existing?.id ? "Save" : "Create loop"}</Button>
    </form>
  );
}

export default function Loops() {
  const [loops, reload] = useFetch("/loops", 15000);
  const [tuningKeys] = useFetch("/loops/tuning-keys", 300000);
  const [templates] = useFetch("/loops/templates", 300000);
  const toast = useToast();
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(null);

  const remove = async (id) => {
    if (!confirm("Delete this loop?")) return;
    try { await del(`/loops/${id}`); toast("Deleted"); reload(); } catch (e) { toast(e.message, "bad"); }
  };

  const runNow = async (l) => {
    try { await api(`/loops/${l.id}/run`, {}); toast(`${l.name} started — running now`); } catch (e) { toast(e.message, "bad"); }
  };

  const useTemplate = (t) => {
    setDraft({ name: "", permissions: t.permissions, input: t.input, output: t.output, target_repo: "", focus: { text: t.focus_text }, tuning: {} });
    setCreating(true);
  };

  return (
    <Card title="Loops" aside={<Button kind={creating ? "secondary" : "primary"} icon={creating ? "x" : "plus"} onClick={() => { setDraft(null); setCreating((c) => !c); }}>{creating ? "Cancel" : "New loop"}</Button>}>
      {!creating && templates && templates.length > 0 && (
        <div className="row tight" style={{ marginBottom: 14 }}>
          <span className="muted small">Start from a template:</span>
          {templates.map((t) => <Button key={t.id} onClick={() => useTemplate(t)}>{t.name}</Button>)}
        </div>
      )}
      {creating && <LoopForm key={draft ? draft.focus.text : "blank"} existing={draft} tuningKeys={tuningKeys} onSaved={() => { setCreating(false); setDraft(null); reload(); }} />}
      {!loops ? <Empty>Loading…</Empty> : (
        <Table rowKey={(l) => l.id} rows={loops} empty="No loops yet. Create one or start from a template."
          cols={[
            { key: "name", label: "Name", render: (l) => <>
                <strong>{l.name}</strong>
                {editing === l.id && <div className="inline-form"><LoopForm existing={l} tuningKeys={tuningKeys} onSaved={() => { setEditing(null); reload(); }} /></div>}
              </> },
            { key: "perm", label: "Can", w: 110, render: (l) => <Chip tone={{ push: "info", files: "ok", read: "" }[l.permissions]}>{{ push: "push PRs", files: "write files", read: "read only" }[l.permissions]}</Chip> },
            { key: "queues", label: "Queues", w: 200, render: (l) => <span className="small">
                {l.input?.type === "queue" ? <>reads <code>{l.input.queue}</code></> : <span className="muted">no input</span>}
                {l.output?.queue ? <> → writes <code>{l.output.queue}</code></> : null}
              </span> },
            { key: "target_repo", label: "Repository", w: 260 },
            { key: "a", label: "", w: 130, render: (l) => <div className="actions">
                <Button kind="ghost" icon="play" aria-label="Run now" title="Run now" onClick={() => runNow(l)} />
                <Button kind="ghost" icon={editing === l.id ? "x" : "edit"} aria-label="Edit" onClick={() => setEditing(editing === l.id ? null : l.id)} />
                <Button kind="ghost danger" icon="trash" aria-label="Delete" onClick={() => remove(l.id)} />
              </div> },
          ]} />
      )}
    </Card>
  );
}
