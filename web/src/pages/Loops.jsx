import React, { useState, useEffect } from "react";
import { api, useFetch, del } from "../api.js";
import { Card, Button, Chip, Empty, Field, Table, useToast } from "../ui.jsx";

function LoopForm({ onSaved, tuningKeys, existing }) {
  const toast = useToast();
  const [form, setForm] = useState(existing || { name: "", role: "producer", target_repo: "", focus: { text: "" }, tuning: {} });
  const [busy, setBusy] = useState(false);
  const [repos, setRepos] = useState(null);
  useEffect(() => { api("/github/repos").then(setRepos).catch(() => {}); }, []); // falls back to text input if not connected
  const set =(k, v) => setForm((f) => ({ ...f, [k]: v }));

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
      <Field label="Name"><input value={form.name} onChange={(e) => set("name", e.target.value)} required /></Field>
      <Field label="Role">
        <select value={form.role} onChange={(e) => set("role", e.target.value)}>
          <option value="producer">Producer — writes backlog items, never pushes</option>
          <option value="consumer">Consumer — implements, pushes, opens a PR</option>
        </select>
      </Field>
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
      <Field label="Focus / prompt">
        <textarea value={form.focus?.text || ""} onChange={(e) => set("focus", { text: e.target.value })} rows={4} required />
      </Field>
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

  const useTemplate = (t) => {
    setDraft({ name: "", role: t.role, target_repo: "", focus: { text: t.focus_text }, tuning: {} });
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
            { key: "role", label: "Role", w: 120, render: (l) => <Chip tone={l.role === "consumer" ? "info" : "ok"}>{l.role}</Chip> },
            { key: "target_repo", label: "Repository", w: 260 },
            { key: "a", label: "", w: 90, render: (l) => <div className="actions">
                <Button kind="ghost" icon={editing === l.id ? "x" : "edit"} aria-label="Edit" onClick={() => setEditing(editing === l.id ? null : l.id)} />
                <Button kind="ghost danger" icon="trash" aria-label="Delete" onClick={() => remove(l.id)} />
              </div> },
          ]} />
      )}
    </Card>
  );
}
