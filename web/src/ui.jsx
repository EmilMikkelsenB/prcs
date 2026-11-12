import React, { createContext, useContext, useState, useCallback } from "react";

const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, kind = "ok") => {
    const id = Math.random();
    setItems((p) => [...p, { id, text, kind }]);
    setTimeout(() => setItems((p) => p.filter((x) => x.id !== id)), kind === "bad" ? 8000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={"toast " + t.kind}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

// 16px stroke icons (lucide-style paths), inherit currentColor.
const PATHS = {
  pulse: "M22 12h-4l-3 9L9 3l-3 9H2",
  loops: "M3 12a9 9 0 0 1 15.5-6.3L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.3L3 16M3 21v-5h5",
  flow: "M5 4h4v4H5zM15 16h4v4h-4zM9 6h4a2 2 0 0 1 2 2v8a2 2 0 0 0 2 2",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5V5a2 2 0 0 1 2-2h14v14H6.5A2.5 2.5 0 0 0 4 19.5z",
  github: "M9 19c-5 1.5-5-2.5-7-3m14 6v-3.9a3.4 3.4 0 0 0-.9-2.6c3.1-.3 6.4-1.5 6.4-7A5.4 5.4 0 0 0 20 4.8 5 5 0 0 0 19.9 1S18.7.7 16 2.5a13.4 13.4 0 0 0-7 0C6.3.7 5.1 1 5.1 1A5 5 0 0 0 5 4.8a5.4 5.4 0 0 0-1.5 3.8c0 5.4 3.3 6.6 6.4 7a3.4 3.4 0 0 0-.9 2.6V22",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4",
  plus: "M12 5v14M5 12h14",
  trash: "M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6",
  edit: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  sync: "M21 12a9 9 0 0 1-15.5 6.3L3 16M3 21v-5h5M3 12a9 9 0 0 1 15.5-6.3L21 8M21 3v5h-5",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  x: "M18 6 6 18M6 6l12 12",
  arrow: "M5 12h14M13 6l6 6-6 6",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
};
export const Icon = ({ name, size = 16, ...p }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...p}><path d={PATHS[name]} /></svg>
);

export const Button = ({ kind = "secondary", busy, icon, children, ...p }) => (
  <button className={"btn " + kind + (children ? "" : " icon-only")} disabled={busy || p.disabled} {...p}>
    {icon && <Icon name={icon} />}{busy ? "…" : children}
  </button>
);

/** Status dot + label. tone: ok | warn | bad | info | "" */
export const Chip = ({ tone = "", children }) => <span className={"chip " + tone}><i className="dot" />{children}</span>;
export const Empty = ({ children }) => <div className="empty">{children}</div>;
export const Card = ({ title, aside, children, className = "" }) => (
  <section className={"panel " + className}>
    {(title || aside) && <header className="panel-h"><h3>{title}</h3><div className="row tight">{aside}</div></header>}
    <div className="panel-b">{children}</div>
  </section>
);

export const Field = ({ label, children }) => (
  <div className="field"><label>{label}</label>{children}</div>
);

/** Dense data table. cols: [{key, label, render?, w?}] */
export const Table = ({ cols, rows, rowKey, onRow, empty }) => (
  rows.length === 0 ? <Empty>{empty}</Empty> : (
    <table className="tbl">
      <thead><tr>{cols.map((c) => <th key={c.key} style={c.w ? { width: c.w } : undefined}>{c.label}</th>)}</tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={rowKey(r)} className={onRow ? "click" : ""} onClick={onRow ? () => onRow(r) : undefined}>
          {cols.map((c) => <td key={c.key}>{c.render ? c.render(r) : r[c.key]}</td>)}
        </tr>
      ))}</tbody>
    </table>
  )
);
