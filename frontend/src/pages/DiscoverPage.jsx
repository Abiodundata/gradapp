import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, query } from "../api";
import { Alert, Empty, Field, Loading, Pagination, ProgramCard } from "../components/ui";
import { Icon } from "../icons";

const FILTER_KEYS = ["search", "degree_level", "funding_available", "max_tuition", "state_or_region", "deadline_open", "ordering"];
const EMPTY_FILTERS = Object.fromEntries(FILTER_KEYS.map((key) => [key, ""]));

/** Search Graduate Programs + Advanced Search/Filter use cases. */
export default function DiscoverPage() {
  const [params, setParams] = useSearchParams();
  const applied = Object.fromEntries(FILTER_KEYS.map((key) => [key, params.get(key) || ""]));
  const page = Number(params.get("page") || 1);
  const [form, setForm] = useState(applied);
  const [data, setData] = useState({ results: [], count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const paramsKey = params.toString();
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setForm(Object.fromEntries(FILTER_KEYS.map((key) => [key, params.get(key) || ""])));
    api(`/programs/${query({ ...Object.fromEntries(params), page: page > 1 ? page : "" })}`)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((err) => { if (!cancelled) { setError(err.message); setData({ results: [], count: 0 }); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  function apply(next = form) {
    const clean = Object.fromEntries(Object.entries(next).filter(([, value]) => value !== ""));
    setParams(clean);
  }
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.type === "checkbox" ? (event.target.checked ? "true" : "") : event.target.value });

  return (
    <div className="dashboard">
      <section className="hero">
        <span className="eyebrow">Graduate program discovery</span>
        <h1>Find a program that fits <em>you.</em></h1>
        <p>Search by program, field, university or city, then narrow down by cost, funding and deadlines.</p>
        <form className="search-bar" role="search" onSubmit={(e) => { e.preventDefault(); apply(); }}>
          <Icon name="search" />
          <input aria-label="Search programs" value={form.search} onChange={set("search")} placeholder="Search programs, fields, universities or cities" />
          <button>Search</button>
        </form>
      </section>
      <section className="content">
        <aside className="filters" aria-label="Filters">
          <div className="filter-heading">
            <h3>Filters</h3>
            <button type="button" onClick={() => { setForm(EMPTY_FILTERS); apply(EMPTY_FILTERS); }}>Clear</button>
          </div>
          <Field label="Degree level">
            <select value={form.degree_level} onChange={set("degree_level")}>
              <option value="">All degrees</option>
              <option value="masters">Master’s</option>
              <option value="doctoral">Doctoral</option>
              <option value="other">Other graduate</option>
            </select>
          </Field>
          <Field label="Funding">
            <select value={form.funding_available} onChange={set("funding_available")}>
              <option value="">Any</option>
              <option value="true">Funding available</option>
              <option value="false">No funding listed</option>
            </select>
          </Field>
          <Field label="Maximum annual tuition">
            <input type="number" min="0" step="1000" placeholder="$40,000" value={form.max_tuition} onChange={set("max_tuition")} />
          </Field>
          <Field label="State or region">
            <input placeholder="e.g. Texas" value={form.state_or_region} onChange={set("state_or_region")} />
          </Field>
          <Field label="Sort by">
            <select value={form.ordering} onChange={set("ordering")}>
              <option value="">University</option>
              <option value="name">Program name</option>
              <option value="tuition">Lowest tuition</option>
              <option value="-tuition">Highest tuition</option>
              <option value="deadline">Earliest deadline</option>
            </select>
          </Field>
          <label className="checkbox">
            <input type="checkbox" checked={form.deadline_open === "true"} onChange={set("deadline_open")} />
            <span>Only open deadlines</span>
          </label>
          <button className="secondary wide" type="button" onClick={() => apply()}>Apply filters</button>
        </aside>
        <section className="results">
          <div className="results-heading">
            <div>
              <h2>Graduate programs</h2>
              <p>{loading ? "Loading programs…" : `${data.count} program${data.count === 1 ? "" : "s"} found`}</p>
            </div>
            <Link className="profile-prompt" to="/recommendations">
              <Icon name="sparkle" />
              <span><strong>Get recommendations</strong>Ranked for your profile</span>
              <Icon name="arrow" />
            </Link>
          </div>
          <Alert>{error}</Alert>
          {loading && <Loading label="Loading programs…" />}
          {!loading && !error && data.results.length === 0 && (
            <Empty title="No programs found">Try different keywords or clear some filters.</Empty>
          )}
          {!loading && (
            <div className="program-list">
              {data.results.map((program) => <ProgramCard key={program.id} program={program} />)}
            </div>
          )}
          <Pagination page={page} count={data.count} onChange={(next) => setParams({ ...Object.fromEntries(params), page: String(next) })} />
        </section>
      </section>
    </div>
  );
}
