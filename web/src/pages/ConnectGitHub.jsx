import React, { useEffect, useState } from "react";
import { api, useFetch } from "../api.js";
import { Card, Chip, Empty, Icon, Table, useToast } from "../ui.jsx";

export default function ConnectGitHub() {
  const [status] = useFetch("/github/status", 30000);
  const [repos, setRepos] = useState(null);
  const toast = useToast();

  useEffect(() => {
    if (status?.connected) api("/github/repos").then(setRepos).catch((e) => toast(e.message, "bad"));
  }, [status?.connected]);

  if (!status) return <Empty>Loading…</Empty>;
  return (
    <Card title="GitHub" aside={<Chip tone={status.connected ? "ok" : "warn"}>{status.connected ? "connected" : "not connected"}</Chip>}>
      {!status.connected ? (
        <>
          <p className="muted small">Connect a GitHub account to pick target repos and let loops push and open PRs.</p>
          <a className="btn primary" href="/auth/github/start"><Icon name="github" />Connect GitHub</a>
        </>
      ) : (
        <>
          <p className="muted small">{repos ? `${repos.length} repos available as loop targets.` : "Loading repos…"}</p>
          {repos && <Table rowKey={(r) => r.full_name} rows={repos} empty="No repositories."
            cols={[{ key: "full_name", label: "Repository" },
                   { key: "private", label: "Visibility", w: 120, render: (r) => r.private ? <span className="chip"><Icon name="lock" size={12} />private</span> : <span className="muted">public</span> }]} />}
        </>
      )}
    </Card>
  );
}
