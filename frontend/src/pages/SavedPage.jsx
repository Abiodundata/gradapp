import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Alert, CompareButton, Empty, Loading, PageHeader, daysLabel, daysUntil, formatDate, formatMoney } from "../components/ui";
import { useSaved } from "../context";
import { Icon } from "../icons";

export const STATUSES = [
  ["interested", "Interested"],
  ["preparing", "Preparing application"],
  ["submitted", "Submitted"],
  ["admitted", "Admitted"],
  ["rejected", "Not admitted"],
  ["withdrawn", "Withdrawn"],
];

function SavedRow({ entry, onChange, onRemove }) {
  const [notes, setNotes] = useState(entry.notes);
  const [state, setState] = useState("");
  const { program } = entry;
  const days = daysUntil(program.application_deadline);

  async function patch(changes) {
    setState("Saving…");
    try {
      const updated = await api(`/saved-programs/${entry.id}/`, { method: "PATCH", body: changes });
      onChange(updated);
      setState("Saved");
      setTimeout(() => setState(""), 1500);
    } catch (err) {
      setState(err.message);
    }
  }

  return (
    <article className="saved-row">
      <div className="saved-main">
        <span className={`status-pill ${entry.status}`}>{entry.status_display}</span>
        <h3><Link to={`/programs/${program.id}`}>{program.name}</Link></h3>
        <p className="muted small">{program.university.name} · {program.university.city}, {program.university.state_or_region}</p>
        <p className="small">
          <Icon name="calendar" size={14} /> {program.application_deadline ? `${formatDate(program.application_deadline)} (${daysLabel(days)})` : "Deadline not listed"}
          {formatMoney(program.tuition_per_year) && <> · <Icon name="money" size={14} /> {formatMoney(program.tuition_per_year)}/yr</>}
        </p>
      </div>
      <div className="saved-controls">
        <label className="field compact-field">
          <span>Status</span>
          <select value={entry.status} onChange={(e) => patch({ status: e.target.value })}>
            {STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="field compact-field">
          <span>My target date</span>
          <input type="date" value={entry.personal_deadline || ""} onChange={(e) => patch({ personal_deadline: e.target.value || null })} />
        </label>
        <label className="field compact-field notes">
          <span>Notes</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== entry.notes && patch({ notes })} placeholder="Letters, essays, contacts…" />
        </label>
      </div>
      <div className="saved-actions">
        <CompareButton program={program} />
        <button className="chip-button danger" onClick={() => onRemove(entry)}><Icon name="trash" size={16} />Remove</button>
        <small className="muted" aria-live="polite">{state}</small>
      </div>
    </article>
  );
}

/** Save Programs use case: shortlist with application status, notes and target dates. */
export default function SavedPage() {
  const { reload } = useSaved();
  const [entries, setEntries] = useState(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api(`/saved-programs/?page_size=100${status ? `&status=${status}` : ""}`)
      .then((data) => setEntries(data.results))
      .catch((err) => setError(err.message));
  }, [status]);
  useEffect(load, [load]);

  async function remove(entry) {
    try {
      await api(`/saved-programs/${entry.id}/`, { method: "DELETE" });
      setEntries((current) => current.filter((item) => item.id !== entry.id));
      reload();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Your shortlist"
        title="Saved programs"
        actions={<Link className="secondary" to="/deadlines"><Icon name="clock" size={17} />View deadlines</Link>}
      >
        Track where you are with each application, add notes, and set your own target dates.
      </PageHeader>
      <div className="segmented" role="group" aria-label="Filter by status">
        <button className={!status ? "active" : ""} onClick={() => setStatus("")}>All</button>
        {STATUSES.map(([value, label]) => (
          <button key={value} className={status === value ? "active" : ""} onClick={() => setStatus(value)}>{label}</button>
        ))}
      </div>
      <Alert>{error}</Alert>
      {!entries && !error && <Loading />}
      {entries && entries.length === 0 && (
        <Empty icon="bookmark" title={status ? "No programs with this status" : "No saved programs yet"} action={<Link className="primary" to="/">Discover programs</Link>}>
          Use the bookmark button on any program to save it here.
        </Empty>
      )}
      <div className="saved-list">
        {entries?.map((entry) => (
          <SavedRow
            key={entry.id}
            entry={entry}
            onRemove={remove}
            onChange={(updated) => setEntries((current) => current.map((item) => (item.id === updated.id ? updated : item)))}
          />
        ))}
      </div>
    </div>
  );
}
