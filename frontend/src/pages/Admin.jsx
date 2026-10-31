import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, withQuery } from '../api.js';
import { useSession } from '../session.jsx';
import { Failed, Field, formData, Loading, PageHead, Status, useAct, useLoad } from '../ui.jsx';

export function Reports() {
  const [params, setParams] = useSearchParams();
  const query = { start: params.get('start') || '', end: params.get('end') || '', criminal: params.get('criminal') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/reports', query));
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={reload} />;

  const { by_status, by_station, period, criminals, history } = data;
  // the two forms share one query string, so each keeps the other's values
  const apply = (extra) => (event) => {
    event.preventDefault();
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries({ ...extra, ...formData(event) })) v ? next.set(k, v) : next.delete(k);
    setParams(next);
  };

  return (
    <>
      <PageHead title="Reports" text="Case counts by status, station and period, and the history of any one person." />
      <div className="cols cols--even">
        <section className="panel">
          <h2>Cases by status</h2>
          {by_status.length ? (
            <table className="data"><thead><tr><th>Status</th><th className="r">Cases</th></tr></thead>
              <tbody>{by_status.map((r) => <tr key={r.status}><td><Status value={r.status} /></td><td className="num r">{r.total}</td></tr>)}</tbody></table>
          ) : <div className="empty"><p>No cases registered yet.</p></div>}
        </section>
        <section className="panel">
          <h2>Cases by station</h2>
          <table className="data"><thead><tr><th>Station</th><th className="r">Cases</th></tr></thead>
            <tbody>{by_station.map((r) => <tr key={r.station}><td>{r.station}</td><td className="num r">{r.total}</td></tr>)}</tbody></table>
        </section>
      </div>

      <section className="panel">
        <h2>Activity in a period</h2>
        <form onSubmit={apply({})}>
          <div className="row">
            <Field label="From" id="start"><input id="start" name="start" type="date" defaultValue={query.start} required /></Field>
            <Field label="To" id="end"><input id="end" name="end" type="date" defaultValue={query.end} required /></Field>
            <button className="btn" type="submit">Run</button>
          </div>
        </form>
        {period && (
          <div className="stats stats--three">
            <div className="stat"><b>{period.complaints}</b><span>Complaints filed</span></div>
            <div className="stat"><b>{period.cases}</b><span>Cases opened</span></div>
            <div className="stat"><b>{period.closed}</b><span>Cases closed</span></div>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Criminal history</h2>
        {criminals.length === 0 ? <p className="muted">There are no criminal records yet.</p> : (
          <form onSubmit={apply({})}>
            <div className="row">
              <Field label="Person" id="criminal">
                <select id="criminal" name="criminal" defaultValue={query.criminal}>
                  {criminals.map((c) => <option key={c.criminal_id} value={c.criminal_id}>{c.name}</option>)}
                </select>
              </Field>
              <button className="btn" type="submit">Show history</button>
            </div>
          </form>
        )}
        {history && (
          <div style={{ marginTop: 'var(--space-lg)' }}>
            <p><b>{history.criminal.name}</b>{history.criminal.crime_history && `: ${history.criminal.crime_history}`}</p>
            {history.cases.length ? (
              <div className="table-wrap"><table className="data" style={{ marginTop: 'var(--space-sm)' }}>
                <thead><tr><th className="r">Case</th><th>Complaint</th><th>Role</th><th>Opened</th><th>Status</th></tr></thead>
                <tbody>{history.cases.map((k) => (
                  <tr key={k.case_id}><td className="num r">{k.case_id}</td><td><Link to={`/cases/${k.case_id}`}>{k.title}</Link></td><td style={{ textTransform: 'capitalize' }}>{k.role}</td><td className="num">{k.date_opened}</td><td><Status value={k.status} /></td></tr>
                ))}</tbody>
              </table></div>
            ) : <p className="muted" style={{ marginTop: 'var(--space-sm)' }}>Not linked to any case.</p>}
          </div>
        )}
      </section>
    </>
  );
}

export function Users() {
  const { user } = useSession();
  const { data, error, loading, reload } = useLoad('/users');
  const act = useAct(reload);
  const [role, setRole] = useState('citizen');
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={reload} />;

  const create = async (event) => {
    const body = formData(event);
    const form = event.target;
    body.station_id = body.station_id ? Number(body.station_id) : null;
    const done = await act(() => api('/users', { method: 'POST', body }), 'Account created.');
    if (done) form.reset();
  };
  const changeRole = (id) => (event) => {
    const body = formData(event);
    return act(() => api(`/users/${id}/role`, { method: 'PUT', body }), 'Role updated.');
  };

  return (
    <>
      <PageHead title="Users" text="Create staff accounts, change roles, and switch accounts off." />
      <section className="panel">
        <h2>Accounts</h2>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Station</th><th>Status</th><th></th></tr></thead>
          <tbody>{data.rows.map((u) => (
            <tr key={u.user_id}>
              <td>{u.name}</td><td>{u.email}</td>
              <td>
                <form className="inline" onSubmit={changeRole(u.user_id)}>
                  <select name="role" aria-label={`Role for ${u.name}`} style={{ width: 'auto' }} defaultValue={u.role} disabled={u.user_id === user.user_id}>
                    {data.roles.map((r) => <option key={r}>{r}</option>)}
                  </select>{' '}
                  {u.user_id !== user.user_id && <button className="link-btn" type="submit">Save</button>}
                </form>
              </td>
              <td>{u.station}</td>
              <td>{u.active ? <span className="badge badge--good">Active</span> : <span className="badge badge--bad">Inactive</span>}</td>
              <td>{u.user_id !== user.user_id && (
                <button className="link-btn" onClick={() => act(() => api(`/users/${u.user_id}/active`, { method: 'POST' }), 'Account updated.')}>
                  {u.active ? 'Deactivate' : 'Activate'}
                </button>
              )}</td>
            </tr>
          ))}</tbody>
        </table></div>
        <p className="muted" style={{ marginTop: 'var(--space-sm)' }}>Officers need a badge, rank and station, so create them with the form below rather than by changing a role.</p>
      </section>

      <section className="panel">
        <h2>New account</h2>
        <form onSubmit={create}>
          <div className="row">
            <Field label="Name" id="n-name"><input id="n-name" name="name" required /></Field>
            <Field label="Email" id="n-email"><input id="n-email" name="email" type="email" required /></Field>
            <Field label="Password" id="n-pass"><input id="n-pass" name="password" type="password" minLength={8} required /></Field>
          </div>
          <div className="row" style={{ marginTop: 'var(--space-md)' }}>
            <Field label="Role" id="n-role">
              <select id="n-role" name="role" value={role} onChange={(e) => setRole(e.target.value)}>{data.roles.map((r) => <option key={r}>{r}</option>)}</select>
            </Field>
            {role === 'officer' && (
              <>
                <Field label="Badge number" id="n-badge"><input id="n-badge" name="badge_no" required /></Field>
                <Field label="Rank" id="n-rank"><input id="n-rank" name="rank" required /></Field>
                <Field label="Station" id="n-station"><select id="n-station" name="station_id">{data.stations.map((s) => <option key={s.station_id} value={s.station_id}>{s.name}</option>)}</select></Field>
              </>
            )}
          </div>
          <button className="btn btn--primary" type="submit" style={{ marginTop: 'var(--space-md)' }}>Create account</button>
        </form>
      </section>
    </>
  );
}
