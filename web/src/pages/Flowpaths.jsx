import React, { useState } from "react";
import { api, useFetch, del } from "../api.js";
import { Card, Button, Empty, Field, useToast } from "../ui.jsx";

function LinkRow({ link, loops, onChange, onRemove }) {
  return (
    <div className="row">
      <select value={link.loop_id} onChange={(e) => onChange({ ...link, loop_id: e.target.value })}>
        <option value="">Pick a loop…</option>
        {loops.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.role})</option>)}
      </select>
      <select value={link.trigger_mode} onChange={(e) => onChange({ ...link, trigger_mode: e.target.value })}>
        <option value="once">once — run once, hand off</option>
        <option value="continuous">continuous — keep its own schedule</option>
      </select>
      <Button kind="danger" type="button" onClick={onRemove}>Remove</Button>
    </div>
  );
}

function FlowpathForm({ loops, onSaved }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [links, setLinks] = useState([{ loop_id: "", trigger_mode: "once" }]);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (links.some((l) => !l.loop_id)) { toast("Pick a loop for every link", "bad"); return; }
    setBusy(true);
    try {
      await api("/flowpaths", { name, links });
      toast("Flowpath created");
      setName("");
      setLinks([{ loop_id: "", trigger_mode: "once" }]);
      onSaved();
    } catch (err) {
      toast(err.message, "bad");
    }
    setBusy(false);
  };

  return (
    <form onSubmit={submit}>
      <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} required /></Field>
      {links.map((link, i) => (
        <LinkRow key={i} link={link} loops={loops}
                 onChange={(l) => setLinks((ls) => ls.map((x, j) => (j === i ? l : x)))}
                 onRemove={() => setLinks((ls) => ls.filter((_, j) => j !== i))} />
      ))}
      <div className="row">
        <Button type="button" onClick={() => setLinks((ls) => [...ls, { loop_id: "", trigger_mode: "once" }])}>Add link</Button>
        <Button kind="primary" busy={busy} type="submit">Create flowpath</Button>
      </div>
    </form>
  );
}

export default function Flowpaths() {
  const [flowpaths, reload] = useFetch("/flowpaths", 15000);
  const [loops] = useFetch("/loops", 300000);
  const toast = useToast();

  const remove = async (id) => {
    if (!confirm("Delete this flowpath?")) return;
    try { await del(`/flowpaths/${id}`); toast("Deleted"); reload(); } catch (e) { toast(e.message, "bad"); }
  };

  if (!loops) return <Empty>Loading…</Empty>;
  return (
    <Card title="Flowpaths">
      {loops.length === 0 ? <Empty>Create at least one loop first.</Empty> : <FlowpathForm loops={loops} onSaved={reload} />}
      {flowpaths && flowpaths.length > 0 && (
        <ul className="list">{flowpaths.map((fp) => (
          <li key={fp.id} className="item">
            <div className="item-top"><b>{fp.name}</b><Button kind="danger" onClick={() => remove(fp.id)}>Delete</Button></div>
            <div className="muted small">
              {fp.links.map((l, i) => {
                const loop = loops.find((x) => x.id === l.loop_id);
                return <span key={i}>{i > 0 && " → "}{loop?.name || l.loop_id} ({l.trigger_mode})</span>;
              })}
            </div>
          </li>
        ))}</ul>
      )}
    </Card>
  );
}
