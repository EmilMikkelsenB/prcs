import React, { useState } from "react";
import { api, useFetch, ago } from "../api.js";
import { Card, Chip, Empty, Table, Button, Markdown, useToast } from "../ui.jsx";

const TONE = { running: "info", done: "ok", failed: "bad", limit_hit: "warn" };
const money = (n) => "$" + (n || 0).toFixed(n >= 10 ? 0 : 2);
const num = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n || 0));
const FAILED = ["failed", "limit_hit"];
const dur = (s) => (s == null ? "–" : s < 60 ? Math.round(s) + "s" : Math.floor(s / 60) + "m " + Math.round(s % 60) + "s");

function Stat({ label, value, sub, tone }) {
  return <div className="stat-tile"><div className="muted small">{label}</div><div className={"stat-val " + (tone || "")}>{value}</div>{sub && <div className="muted small">{sub}</div>}</div>;
}

function useRetry() {
  const toast = useToast();
  return async (id) => {
    try { await api(`/runs/${id}/retry`, {}); toast("Started — running now"); return true; }
    catch (e) { toast(e.message, "bad"); return false; }
  };
}

function RunDetail({ id, onClose }) {
  const [r] = useFetch("/runs/" + id, 3000);
  const retry = useRetry();
  if (!r) return <Card title="Run"><Empty>Loading…</Empty></Card>;
  const st = r.stats;
  return (
    <Card title={r.loop?.name || "Run " + id} aside={<>
      <Chip tone={TONE[r.status]}>{r.status}</Chip>
      {FAILED.includes(r.status) && <Button icon="retry" onClick={() => retry(id)}>Run again now</Button>}
      <Button kind="ghost" icon="x" aria-label="Close" onClick={onClose} />
    </>}>
      <p className="muted small">{r.loop?.target_repo} · started {ago(r.started_at)}{r.secs != null && ` · ${dur(r.secs)}`}</p>
      {st && <p className="small">{money(st.cost_usd)} · {num(st.input_tokens)} in / {num(st.output_tokens)} out · {num(st.cache_read_tokens)} cached · {st.turns} turns</p>}
      {r.output?.pr_url && <p className="small"><a href={r.output.pr_url} target="_blank" rel="noreferrer">{r.output.pr_url}</a></p>}
      {r.output?.new_files?.length > 0 && <p className="small muted">New files: {r.output.new_files.join(", ")}</p>}
      <h4 className="sect">Output</h4>
      {r.log_tail ? <Markdown text={r.log_tail} /> : <Empty>{r.status === "running" ? "Running… the output appears when the run finishes." : "No output."}</Empty>}
    </Card>
  );
}

export default function Overview({ go }) {
  const [runs] = useFetch("/runs", 4000);
  const [usage] = useFetch("/usage", 15000);
  const [loops] = useFetch("/loops", 30000);
  const [runner] = useFetch("/runner", 15000);
  const [kb] = useFetch("/kb?q=", 30000);
  const [qs] = useFetch("/queues", 8000);
  const [sel, setSel] = useState(null);
  const retry = useRetry();

  const list = Array.isArray(runs) ? runs : [];
  const running = list.filter((r) => r.status === "running").length;
  const t = usage?.today;
  const rn = runner?.runner;
  // latest run per loop; retry only loops whose latest run failed (older failures are history)
  const latest = {};
  for (const r of list) if (!latest[r.loop?.id]) latest[r.loop?.id] = r;
  const failedNow = Object.values(latest).filter((r) => r.loop?.id && FAILED.includes(r.status));
  const retryAll = async () => { for (const r of failedNow) await retry(r.id); };

  return (
    <>
      <div className="stats">
        <Stat label="Running now" value={running} tone={running ? "info" : ""} sub={`${loops?.length ?? "–"} loops defined`} />
        <Stat label="Runs, last 24h" value={t?.runs ?? "–"} sub={t ? `${t.failed} failed` : ""} tone={t?.failed ? "bad" : ""} />
        <Stat label="Cost, last 24h" value={t ? money(t.cost_usd) : "–"} sub={usage ? `${money(usage.week.cost_usd)} this week` : ""} />
        <Stat label="Tokens, last 24h" value={t ? num(t.input_tokens + t.output_tokens) : "–"} sub={t ? `${num(t.cache_read_tokens)} cached` : ""} />
        <Stat label="Claude CLI" value={rn?.claude_version?.split(" ")[0] || (rn?.ok ? "?" : "offline")}
              sub={rn?.ok ? (rn.logged_in ? "signed in" : "not signed in — run claude login") : "runner unreachable"} tone={rn?.ok && rn.logged_in ? "" : "warn"} />
      </div>

      <div className="split">
        <Card title="Runs" aside={<>{failedNow.length > 0 && <Button icon="retry" onClick={retryAll}>Run {failedNow.length} failed again now</Button>}<span className="muted small">since the runner last started</span></>}>
          {runs && runs.error ? <Empty>{runs.error}</Empty> : (
            <Table rowKey={(r) => r.id} rows={list} onRow={(r) => setSel(r.id)} empty="No runs yet. They appear here once a flowpath triggers a loop."
              cols={[
                { key: "loop", label: "Loop", render: (r) => <strong>{r.loop?.name || r.id}</strong> },
                { key: "status", label: "Status", w: 110, render: (r) => <Chip tone={TONE[r.status]}>{r.status}</Chip> },
                { key: "started", label: "Started", w: 100, render: (r) => ago(r.started_at) },
                { key: "secs", label: "Time", w: 80, render: (r) => dur(r.secs ?? (Date.now() / 1000 - r.started_at)) },
                { key: "cost", label: "Cost", w: 70, render: (r) => (r.stats ? money(r.stats.cost_usd) : "–") },
                { key: "a", label: "", w: 44, render: (r) => FAILED.includes(r.status) && r.loop?.id
                    ? <div className="actions" onClick={(e) => e.stopPropagation()}><Button kind="ghost" icon="retry" aria-label="Run again now" title="Run again now" onClick={() => retry(r.id)} /></div> : null },
              ]} />
          )}
        </Card>
        {sel ? <RunDetail id={sel} onClose={() => setSel(null)} /> : (
          <Card title="Usage by loop">
            <Table rowKey={(r) => r.loop} rows={usage?.by_loop || []} empty="Usage is recorded as flowpath runs finish."
              cols={[
                { key: "loop", label: "Loop" },
                { key: "runs", label: "Runs", w: 60 },
                { key: "tok", label: "Tokens", w: 90, render: (r) => num(r.input_tokens + r.output_tokens) },
                { key: "cost", label: "Cost", w: 80, render: (r) => money(r.cost_usd) },
              ]} />
          </Card>
        )}
      </div>

      <Card title="Queues" aside={<Button kind="ghost" onClick={() => go("Knowledge base")}>Open KB</Button>}>
        <Table rowKey={(q) => q.repo + q.queue} rows={Array.isArray(qs) ? qs : []} empty="No queues yet. A loop with an output queue creates one when it finishes."
          cols={[
            { key: "repo", label: "Repository" },
            { key: "queue", label: "Queue", render: (q) => <code>{q.queue}</code> },
            { key: "pending", label: "Waiting", w: 90, render: (q) => <strong>{q.pending}</strong> },
            { key: "in_progress", label: "Running", w: 90 },
            { key: "done", label: "Done", w: 90 },
          ]} />
      </Card>

      <Card title="Recent knowledge" aside={<Button kind="ghost" onClick={() => go("Knowledge base")}>Open KB</Button>}>
        <Table rowKey={(f) => f.path} rows={(Array.isArray(kb) ? kb : []).slice(0, 6)} empty="Nothing yet — runs and repo syncs write here."
          cols={[{ key: "title", label: "Title" }, { key: "path", label: "Path", render: (f) => <span className="muted">{f.path}</span> }]} />
      </Card>
    </>
  );
}
