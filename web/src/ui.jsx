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

export const Button = ({ kind = "secondary", busy, children, ...p }) => (
  <button className={"btn " + kind} disabled={busy || p.disabled} {...p}>{busy ? "…" : children}</button>
);

export const Chip = ({ tone = "", children }) => <span className={"chip " + tone}>{children}</span>;
export const Empty = ({ children }) => <div className="empty">{children}</div>;
export const Card = ({ title, aside, children, className = "" }) => (
  <section className={"card " + className}>
    {(title || aside) && <header className="card-h"><h3>{title}</h3><div>{aside}</div></header>}
    {children}
  </section>
);

export const Field = ({ label, children }) => (
  <div className="field"><label>{label}</label>{children}</div>
);
