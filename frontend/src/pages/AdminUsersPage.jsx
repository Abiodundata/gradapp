import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { API_URL, api, query } from "../api";
import { Alert, Loading, PageHeader, Pagination, formatDate } from "../components/ui";
import { useAuth } from "../context";
import { Icon } from "../icons";

/** Manage Users use case (GradApp Administrator). */
export default function AdminUsersPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({ search: "", is_active: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(() => {
    api(`/admin/users/${query({ ...filters, page: page > 1 ? page : "" })}`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [filters, page]);
  useEffect(() => { if (user?.is_staff) load(); }, [load, user]);

  if (!user?.is_staff) return <Navigate to="/" replace />;

  async function update(account, changes) {
    setBusyId(account.id);
    setError("");
    try {
      const updated = await api(`/admin/users/${account.id}/`, { method: "PATCH", body: changes });
      setData((current) => ({ ...current, results: current.results.map((item) => (item.id === updated.id ? updated : item)) }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="page wide-page">
      <PageHeader
        eyebrow="Administration"
        title="Manage users"
        actions={<a className="secondary" href={API_URL.replace(/\/api\/?$/, "/admin/")} target="_blank" rel="noreferrer">Data admin<Icon name="external" size={16} /></a>}
      >
        Activate or deactivate accounts and manage administrator access. Program, faculty and funding records are managed in the data admin.
      </PageHeader>
      <form className="toolbar" role="search" onSubmit={(e) => { e.preventDefault(); setFilters({ ...filters, search }); setPage(1); }}>
        <div className="toolbar-search">
          <Icon name="search" />
          <input aria-label="Search users" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by username, name or email" />
        </div>
        <button className="primary">Search</button>
        <select aria-label="Account status" value={filters.is_active} onChange={(e) => { setFilters({ ...filters, is_active: e.target.value }); setPage(1); }}>
          <option value="">All accounts</option>
          <option value="true">Active</option>
          <option value="false">Deactivated</option>
        </select>
      </form>
      <Alert>{error}</Alert>
      {!data && !error && <Loading label="Loading users…" />}
      {data && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">User</th>
                <th scope="col">Email</th>
                <th scope="col">Joined</th>
                <th scope="col">Last sign-in</th>
                <th scope="col">Saved</th>
                <th scope="col">Active</th>
                <th scope="col">Administrator</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((account) => {
                const self = account.id === user.id;
                return (
                  <tr key={account.id} className={account.is_active ? "" : "inactive"}>
                    <td><strong>{account.username}</strong><small>{[account.first_name, account.last_name].filter(Boolean).join(" ")}{self && " (you)"}</small></td>
                    <td>{account.email || "—"}</td>
                    <td>{formatDate(account.date_joined.slice(0, 10))}</td>
                    <td>{account.last_login ? formatDate(account.last_login.slice(0, 10)) : "Never"}</td>
                    <td>{account.saved_program_count}</td>
                    <td>
                      <label className="switch-control">
                        <input type="checkbox" checked={account.is_active} disabled={self || busyId === account.id} onChange={(e) => update(account, { is_active: e.target.checked })} aria-label={`${account.username} active`} />
                        <span />
                      </label>
                    </td>
                    <td>
                      <label className="switch-control">
                        <input type="checkbox" checked={account.is_staff} disabled={self || busyId === account.id} onChange={(e) => update(account, { is_staff: e.target.checked })} aria-label={`${account.username} administrator`} />
                        <span />
                      </label>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pagination page={page} count={data.count} onChange={setPage} />}
    </div>
  );
}
