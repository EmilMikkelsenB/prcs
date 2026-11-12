import { useEffect, useState, useCallback } from "react";

export async function api(path, body, method) {
  const opt = body === undefined
    ? { method: method || "GET" }
    : { method: method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch("/api" + path, opt);
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { window.dispatchEvent(new Event("auth:required")); throw new Error("not logged in"); }
  if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}

export const del = (path) => api(path, {}, "DELETE");

/** Poll a GET endpoint. Returns [data, reload, error]. */
export function useFetch(path, ms = 5000) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const load = useCallback(() => api(path).then((x) => { setD(x); setErr(null); }).catch(setErr), [path]);
  useEffect(() => {
    load();
    const t = setInterval(load, ms);
    return () => clearInterval(t);
  }, [load, ms]);
  return [d, load, err];
}

/** "4m ago" from epoch seconds or an ISO string. */
export function ago(t) {
  const s = typeof t === "string" ? Date.parse(t) / 1000 : t;
  if (!s) return "never";
  const d = Math.max(0, Date.now() / 1000 - s);
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}
