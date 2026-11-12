import React, { useEffect, useState } from "react";
import { api, useFetch } from "../api.js";
import { Card, Chip, Empty, useToast } from "../ui.jsx";

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
          <a className="btn primary" href="/auth/github/start">Connect GitHub</a>
        </>
      ) : (
        <>
          <p className="muted small">{repos ? `${repos.length} repos available as loop targets.` : "Loading repos…"}</p>
          {repos && (
            <ul className="list">{repos.map((r) => (
              <li key={r.full_name} className="item"><b>{r.full_name}</b> {r.private && <Chip>private</Chip>}</li>
            ))}</ul>
          )}
        </>
      )}
    </Card>
  );
}
