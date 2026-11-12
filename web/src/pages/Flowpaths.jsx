import React, { useState } from "react";
import { api, useFetch, del } from "../api.js";
import { Card, Button, Empty, Field, Icon, Table, useToast } from "../ui.jsx";

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
      <Button kind="ghost danger" icon="x" type="button" aria-label="Remove link" onClick={onRemove} />
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
        <Button type="button" icon="plus" onClick={() => setLinks((ls) => [...ls, { loop_id: "", trigger_mode: "once" }])}>Add link</Button>
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
  const name = (id) => loops.find((x) => x.id === id)?.name || id;
  return (
    <>
      <Card title="Flowpaths">
        {!flowpaths ? <Empty>Loading…</Empty> : (
          <Table rowKey={(fp) => fp.id} rows={flowpaths} empty="No flowpaths yet. Chain loops below."
            cols={[
              { key: "name", label: "Name", w: 220, render: (fp) => <strong>{fp.name}</strong> },
              { key: "chain", label: "Chain", render: (fp) => <span className="row tight">
                  {fp.links.map((l, i) => <React.Fragment key={i}>
                    {i > 0 && <Icon name="arrow" size={14} />}
                    <span>{name(l.loop_id)} <span className="muted small">({l.trigger_mode})</span></span>
                  </React.Fragment>)}
                </span> },
              { key: "a", label: "", w: 60, render: (fp) => <div className="actions"><Button kind="ghost danger" icon="trash" aria-label="Delete" onClick={() => remove(fp.id)} /></div> },
            ]} />
        )}
      </Card>
      <Card title="New flowpath">
        {loops.length === 0 ? <Empty>Create at least one loop first.</Empty> : <FlowpathForm loops={loops} onSaved={reload} />}
      </Card>
    </>
  );
}
