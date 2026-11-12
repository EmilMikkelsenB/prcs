import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { ToastProvider } from "./ui.jsx";
import Login from "./pages/Login.jsx";
import RunnerSetup from "./pages/RunnerSetup.jsx";
import ConnectGitHub from "./pages/ConnectGitHub.jsx";
import Loops from "./pages/Loops.jsx";
import Flowpaths from "./pages/Flowpaths.jsx";

const TABS = ["Loops", "Flowpaths", "GitHub"];

export default function App() {
  const [authed, setAuthed] = useState(null); // null = still checking
  const [runnerConfigured, setRunnerConfigured] = useState(null);
  const [suggestedRunnerUrl, setSuggestedRunnerUrl] = useState("");
  const [tab, setTab] = useState("Loops");

  useEffect(() => {
    api("/loops").then(() => setAuthed(true)).catch(() => setAuthed(false));
    const onAuthRequired = () => setAuthed(false);
    window.addEventListener("auth:required", onAuthRequired);
    return () => window.removeEventListener("auth:required", onAuthRequired);
  }, []);

  useEffect(() => {
    if (!authed) return;
    api("/config").then((c) => {
      setSuggestedRunnerUrl(c.runner_url);
      setRunnerConfigured(c.runner_url_configured);
    }).catch(() => setRunnerConfigured(true)); // fail open, don't block on a transient error
  }, [authed]);

  if (authed === null) return null;
  if (!authed) return <ToastProvider><Login onLoggedIn={() => setAuthed(true)} /></ToastProvider>;
  if (runnerConfigured === null) return null;
  if (!runnerConfigured) {
    return <ToastProvider>
      <RunnerSetup suggested={suggestedRunnerUrl} onSaved={() => setRunnerConfigured(true)} />
    </ToastProvider>;
  }

  const logout = async () => { await fetch("/auth/logout", { method: "POST" }); setAuthed(false); };

  return (
    <ToastProvider>
      <header className="top">
        <h1 className="brand">Agent Loop Dash</h1>
        <nav>{TABS.map((t) => (
          <button key={t} className={"nav" + (t === tab ? " on" : "")} onClick={() => setTab(t)}>{t}</button>
        ))}</nav>
        <button className="btn" onClick={logout}>Sign out</button>
      </header>
      <main>
        {tab === "Loops" && <Loops />}
        {tab === "Flowpaths" && <Flowpaths />}
        {tab === "GitHub" && <ConnectGitHub />}
      </main>
    </ToastProvider>
  );
}
