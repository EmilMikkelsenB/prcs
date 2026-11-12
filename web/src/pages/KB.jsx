import React, { useEffect, useState } from "react";
import { api, del, ago } from "../api.js";
import { Card, Button, Chip, Empty, Field, Icon, Markdown, useToast } from "../ui.jsx";

const TONE = { done: "ok", failed: "bad", limit_hit: "warn" };

/** Parse a runs/ note (see kb.save_run) into parts; null for anything else so it renders as plain markdown. */
function parseRun(path, text) {
  if (!path.startsWith("runs/")) return null;
  const m = text.match(/^# (.+) - (\w+)\n\n([\s\S]*?)\n\n---\n\n## Run details\n\n([\s\S]*)$/);
  if (!m) return null;
  const [, name, status, result, details] = m;
  const line = (k) => (details.match(new RegExp("^- " + k + ": (.*)$", "m")) || [])[1];
  let out = {};
  try { out = JSON.parse((details.match(/```json\n([\s\S]*?)\n```/) || [])[1] || "{}"); } catch { /* keep {} */ }
  return { name, status, result, repo: line("repo"), cost: line("cost"), exit: line("exit code"), out, details };
}

function RunNote({ run }) {
  const o = run.out || {};
  const files = Array.isArray(o.files) ? o.files : Object.keys(o.files || {});
  return (
    <>
      <div className="run-head">
        <Chip tone={TONE[run.status]}>{run.status}</Chip>
        <span className="muted small">{run.repo}</span>
        <span className="muted small">{run.cost}</span>
      </div>
      {(o.pr_url || o.commit || files.length > 0) && (
        <div className="run-links">
          {o.pr_url && <a className="pill" href={o.pr_url} target="_blank" rel="noreferrer">Pull request ↗</a>}
          {o.commit && <span className="pill">commit {o.commit.slice(0, 7)}</span>}
          {files.map((f) => <span key={f} className="pill">{f}</span>)}
        </div>
      )}
      <div className="run-result"><Markdown text={run.result} /></div>
      <details className="run-raw">
        <summary>Technical details</summary>
        <pre className="kb-view">{run.details}</pre>
      </details>
    </>
  );
}

export default function KB() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState(null);
  const [open, setOpen] = useState(null); // {path, content, editable, draft}
  const [busy, setBusy] = useState(false);
  const [src, setSrc] = useState(false); // false = rendered markdown

  const list = (query = q) => api("/kb?q=" + encodeURIComponent(query)).then(setFiles).catch((e) => toast(e.message, "bad"));
  const loadStatus = () => api("/kb/status").then(setStatus).catch(() => {});
  useEffect(() => { list(""); loadStatus(); }, []);
  useEffect(() => { const t = setTimeout(() => list(q), 250); return () => clearTimeout(t); }, [q]);

  const view = (path) => api("/kb/file?path=" + encodeURIComponent(path))
    .then((f) => setOpen({ ...f, draft: f.content })).catch((e) => toast(e.message, "bad"));

  const sync = async () => {
    setBusy(true);
    try {
      const r = await api("/kb/sync", {});
      const errs = Object.entries(r.results).filter(([, v]) => typeof v === "string");
      toast(errs.length ? `Synced with errors: ${errs[0][1]}` : `Synced ${Object.keys(r.results).length} repo(s)`, errs.length ? "bad" : "ok");
      list(); loadStatus();
    } catch (e) { toast(e.message, "bad"); }
    setBusy(false);
  };

  const save = async () => {
    try {
      await api("/kb/file", { path: open.path, content: open.draft });
      toast("Note saved");
      setOpen({ ...open, content: open.draft });
      list();
    } catch (e) { toast(e.message, "bad"); }
  };

  const remove = async () => {
    if (!window.confirm(`Delete ${open.path}?`)) return;
    try { await del("/kb/file?path=" + encodeURIComponent(open.path)); setOpen(null); list(); } catch (e) { toast(e.message, "bad"); }
  };

  return (
    <>
      <Card title="Knowledge base"
            aside={<>
              <Button icon="plus" onClick={() => setOpen({ path: "notes/untitled.md", content: "", draft: "", editable: true, isNew: true })}>New note</Button>
              <Button kind="primary" icon="sync" busy={busy} onClick={sync}>Sync repos</Button>
            </>}>
        <p className="muted small">
          Plain files in <code>{status?.dir || "/app/kb"}</code> — also on disk at your <code>KB_PATH</code> folder. Repo docs and run
          results land here automatically; anything under <code>notes/</code> is yours to edit.
          Last sync: {status?.last_sync ? ago(status.last_sync) : "never"}
          {status?.interval ? ` · every ${Math.round(status.interval / 60)} min` : " · manual only"}
        </p>
        <label className="search"><Icon name="search" /><input type="search" placeholder="Search files and notes" value={q} onChange={(e) => setQ(e.target.value)} /></label>
      </Card>

      <div className="split">
        <div>
      {files.length === 0 ? <Empty>{q ? "No matches." : "Nothing here yet — sync repos or add a note."}</Empty> : (
        <ul className="list">
          {files.map((f) => (
            <li key={f.path}>
              <button className="item" onClick={() => view(f.path)}>
                <div className="item-top"><strong><Icon name={f.editable ? "edit" : "file"} size={13} /> {f.title}</strong>{f.editable && <Chip tone="info">note</Chip>}</div>
                <div className="muted small clip">{f.path}</div>
                {f.snippet && <div className="small">{f.snippet}</div>}
              </button>
            </li>
          ))}
        </ul>
      )}
        </div>
        {open ? (
        <Card title={open.path} aside={<><div className="seg" role="group" aria-label="View"><button className={src ? "" : "on"} onClick={() => setSrc(false)}>Preview</button><button className={src ? "on" : ""} onClick={() => setSrc(true)}>Source</button></div><Button kind="ghost" icon="x" aria-label="Close" onClick={() => setOpen(null)} /></>}>
          {open.editable ? (
            <>
              {open.isNew && (
                <Field label="Path (under notes/)">
                  <input value={open.path} onChange={(e) => setOpen({ ...open, path: e.target.value })} />
                </Field>
              )}
              {src || open.isNew
                ? <textarea rows={14} value={open.draft} onChange={(e) => setOpen({ ...open, draft: e.target.value })} />
                : <Markdown text={open.draft} />}
              <div className="row">
                <Button kind="primary" onClick={save} disabled={open.draft === open.content && !open.isNew}>Save</Button>
                {!open.isNew && <Button kind="danger" icon="trash" onClick={remove}>Delete</Button>}
              </div>
            </>
          ) : (
            <>
              <p className="muted small">Read-only mirror — it's overwritten on the next sync. Copy it into <code>notes/</code> to edit.</p>
              {src ? <pre className="kb-view">{open.content}</pre> : (parseRun(open.path, open.content) ? <RunNote run={parseRun(open.path, open.content)} /> : <Markdown text={open.content} />)}
            </>
          )}
        </Card>
      ) : <Card title="File"><Empty>Select a file to read it, or create a note.</Empty></Card>}
      </div>
    </>
  );
}
