import React, { useEffect, useState } from "react";
import { api, useFetch } from "./api.js";
import { ToastProvider, Icon } from "./ui.jsx";
import Login from "./pages/Login.jsx";
import RunnerSetup from "./pages/RunnerSetup.jsx";
import ConnectGitHub from "./pages/ConnectGitHub.jsx";
import Overview from "./pages/Overview.jsx";
import Loops from "./pages/Loops.jsx";
import Flowpaths from "./pages/Flowpaths.jsx";
import KB from "./pages/KB.jsx";
import Settings from "./pages/Settings.jsx";

const PAGES = [
  { id: "Overview", icon: "pulse", el: null },
  { id: "Loops", icon: "loops", el: <Loops /> },
  { id: "Flowpaths", icon: "flow", el: <Flowpaths /> },
  { id: "Knowledge base", icon: "book", el: <KB /> },
  { id: "GitHub", icon: "github", el: <ConnectGitHub /> },
  { id: "Settings", icon: "settings", el: <Settings /> },
];

function useTheme() {
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem("theme"); } catch { return null; } });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme;
    try { theme ? localStorage.setItem("theme", theme) : localStorage.removeItem("theme"); } catch { /* private mode */ }
  }, [theme]);
  const dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  return [dark, () => setTheme(dark ? "light" : "dark")];
}

function SideStatus() {
  const [runner] = useFetch("/runner", 15000);
  const [gh] = useFetch("/github/status", 60000);
  const tone = (ok) => (ok == null ? "" : ok ? "ok" : "bad");
  return (
    <>
      <div className={"stat chip " + tone(runner?.runner?.ok)}><i className="dot" />Runner {runner ? (runner.runner?.ok ? "online" : "unreachable") : "…"}</div>
      <div className={"stat chip " + (gh ? (gh.connected ? "ok" : "warn") : "")}><i className="dot" />GitHub {gh ? (gh.connected ? "connected" : "not connected") : "…"}</div>
    </>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(null); // null = still checking
  const [runnerConfigured, setRunnerConfigured] = useState(null);
  const [suggestedRunnerUrl, setSuggestedRunnerUrl] = useState("");
  const [tab, setTab] = useState("Overview");
  const [dark, toggleTheme] = useTheme();

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
  const page = PAGES.find((p) => p.id === tab);

  return (
    <ToastProvider>
      <div className="shell">
        <aside className="side">
          <div className="brand"><span className="mark"><Icon name="loops" size={14} /></span>Wellqon Cadence</div>
          <nav aria-label="Sections">{PAGES.map((p) => (
            <button key={p.id} className={"nav" + (p.id === tab ? " on" : "")} onClick={() => setTab(p.id)} aria-current={p.id === tab ? "page" : undefined}>
              <Icon name={p.icon} />{p.id}
            </button>
          ))}</nav>
          <div className="foot">
            <SideStatus />
            <button className="nav" onClick={toggleTheme}><Icon name={dark ? "sun" : "moon"} />{dark ? "Light theme" : "Dark theme"}</button>
            <button className="nav" onClick={logout}><Icon name="logout" />Sign out</button>
          </div>
        </aside>
        <div className="content">
          <div className="topbar"><h1>{tab}</h1></div>
          <main>{tab === "Overview" ? <Overview go={setTab} /> : page.el}</main>
        </div>
      </div>
    </ToastProvider>
  );
}
