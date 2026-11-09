import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, withQuery } from '../api.js';
import { Bars, Line } from '../charts.jsx';
import { useSession } from '../session.jsx';
import { Empty, Failed, Field, Filters, formData, Loading, PageHead, Pager, Status, useAct, useLoad } from '../ui.jsx';
import { useT } from '../i18n.jsx';

export function Reports() {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const query = { start: params.get('start') || '', end: params.get('end') || '', criminal: params.get('criminal') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/reports', query));
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={reload} />;

  const { by_status, by_station, period, criminals, history, monthly, by_category, by_severity } = data;
  // the two forms share one query string, so each keeps the other's values
  const apply = (extra) => (event) => {
    event.preventDefault();
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries({ ...extra, ...formData(event) })) v ? next.set(k, v) : next.delete(k);
    setParams(next);
  };

  return (
    <>
      <PageHead title={t('Reports')} text="Case counts by status, station and period, and the history of any one person." />
      <section className="panel">
        <h2>{t('Complaints filed, last 12 months')}</h2>
        <Line points={monthly} title={t('Complaints filed per month')} />
      </section>

      <div className="cols cols--even">
        <section className="panel">
          <h2>{t('Complaints by category')}</h2>
          {by_category.length ? <Bars rows={by_category} label="category" value="total" title={t('Complaints by category')} /> : <div className="empty"><p>{t('No complaints yet.')}</p></div>}
        </section>
        <section className="panel">
          <h2>{t('Complaints by severity')}</h2>
          {by_severity.length ? <Bars rows={by_severity} label="severity" value="total" title={t('Complaints by severity')} /> : <div className="empty"><p>{t('No complaints yet.')}</p></div>}
        </section>
      </div>

      <div className="cols cols--even">
        <section className="panel">
          <h2>{t('Cases by status')}</h2>
          {by_status.length ? (
            <Bars rows={by_status} label="status" value="total" title={t('Cases by status')} />
          ) : <div className="empty"><p>{t('No cases registered yet.')}</p></div>}
        </section>
        <section className="panel">
          <h2>{t('Cases by station')}</h2>
          <Bars rows={by_station} label="station" value="total" title={t('Cases by station')} />
        </section>
      </div>

      <section className="panel">
        <h2>{t('Activity in a period')}</h2>
        <form onSubmit={apply({})}>
          <div className="row">
            <Field label="From" id="start"><input id="start" name="start" type="date" defaultValue={query.start} required /></Field>
            <Field label="To" id="end"><input id="end" name="end" type="date" defaultValue={query.end} required /></Field>
            <button className="btn" type="submit">{t('Run')}</button>
          </div>
        </form>
        {period && (
          <div className="stats stats--three">
            <div className="stat"><b>{period.complaints}</b><span>{t('Complaints filed')}</span></div>
            <div className="stat"><b>{period.cases}</b><span>{t('Cases opened')}</span></div>
            <div className="stat"><b>{period.closed}</b><span>{t('Cases closed')}</span></div>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>{t('Criminal history')}</h2>
        {criminals.length === 0 ? <p className="muted">{t('There are no criminal records yet.')}</p> : (
          <form onSubmit={apply({})}>
            <div className="row">
              <Field label="Person" id="criminal">
                <select id="criminal" name="criminal" defaultValue={query.criminal}>
                  {criminals.map((c) => <option key={c.criminal_id} value={c.criminal_id}>{c.name}</option>)}
                </select>
              </Field>
              <button className="btn" type="submit">{t('Show history')}</button>
            </div>
          </form>
        )}
        {history && (
          <div style={{ marginTop: 'var(--space-lg)' }}>
            <p><b>{history.criminal.name}</b>{history.criminal.crime_history && `: ${history.criminal.crime_history}`}</p>
            {history.cases.length ? (
              <div className="table-wrap"><table className="data" style={{ marginTop: 'var(--space-sm)' }}>
                <thead><tr><th className="r">{t('Case')}</th><th>{t('Complaint')}</th><th>{t('Role')}</th><th>{t('Opened')}</th><th>{t('Status')}</th></tr></thead>
                <tbody>{history.cases.map((k) => (
                  <tr key={k.case_id}><td className="num r">{k.case_id}</td><td><Link to={`/cases/${k.case_id}`}>{k.title}</Link></td><td style={{ textTransform: 'capitalize' }}>{t(k.role)}</td><td className="num">{k.date_opened}</td><td><Status value={k.status} /></td></tr>
                ))}</tbody>
              </table></div>
            ) : <p className="muted" style={{ marginTop: 'var(--space-sm)' }}>{t('Not linked to any case.')}</p>}
          </div>
        )}
      </section>
    </>
  );
}

export function Users() {
  const t = useT();
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
  const addStation = async (event) => {
    const body = formData(event);
    const form = event.target;
    for (const key of ['latitude', 'longitude']) body[key] = body[key] === '' ? null : Number(body[key]);
    const done = await act(() => api('/stations', { method: 'POST', body }), 'Station added.');
    if (done) form.reset();
  };
  const changeRole = (id) => (event) => {
    const body = formData(event);
    return act(() => api(`/users/${id}/role`, { method: 'PUT', body }), 'Role updated.');
  };

  return (
    <>
      <PageHead title={t('Users')} text="Create staff accounts, change roles, and switch accounts off." />
      <section className="panel">
        <h2>{t('Accounts')}</h2>
        <div className="table-wrap"><table className="data">
          <thead><tr><th>{t('Name')}</th><th>{t('Email')}</th><th>{t('Role')}</th><th>{t('Station')}</th><th>{t('Status')}</th><th></th></tr></thead>
          <tbody>{data.rows.map((u) => (
            <tr key={u.user_id}>
              <td>{u.name}</td><td>{u.email}</td>
              <td>
                <form className="inline" onSubmit={changeRole(u.user_id)}>
                  <select name="role" aria-label={t('Role for {name}', { name: u.name })} style={{ width: 'auto' }} defaultValue={u.role} disabled={u.user_id === user.user_id}>
                    {data.roles.map((r) => <option key={r} value={r}>{t(r)}</option>)}
                  </select>{' '}
                  {u.user_id !== user.user_id && <button className="link-btn" type="submit">{t('Save')}</button>}
                </form>
              </td>
              <td>{u.station}</td>
              <td>{u.active ? <span className="badge badge--good">{t('Active')}</span> : <span className="badge badge--bad">{t('Inactive')}</span>}</td>
              <td>{u.user_id !== user.user_id && (
                <button className="link-btn" onClick={() => act(() => api(`/users/${u.user_id}/active`, { method: 'POST' }), 'Account updated.')}>
                  {t(u.active ? 'Deactivate' : 'Activate')}
                </button>
              )}</td>
            </tr>
          ))}</tbody>
        </table></div>
        <p className="muted" style={{ marginTop: 'var(--space-sm)' }}>{t('Officers need a badge, rank and station, so create them with the form below rather than by changing a role.')}</p>
      </section>

      <section className="panel">
        <h2>{t('Police stations')}</h2>
        {data.stations.length ? (
          <div className="table-wrap"><table className="data">
            <thead><tr><th>{t('Station')}</th><th>{t('Area covered')}</th></tr></thead>
            <tbody>{data.stations.map((s) => <tr key={s.station_id}><td>{s.name}</td><td>{s.jurisdiction}</td></tr>)}</tbody>
          </table></div>
        ) : <p className="muted">{t('No stations yet. Add one before creating officers or registering cases.')}</p>}
        <form onSubmit={addStation} style={{ marginTop: 'var(--space-md)' }}>
          <div className="row">
            <Field label="Station name" id="s-name"><input id="s-name" name="name" required /></Field>
            <Field label="Area covered" id="s-area"><input id="s-area" name="jurisdiction" required /></Field>
            <Field label="Phone" id="s-phone"><input id="s-phone" name="phone" /></Field>
          </div>
          <div className="row" style={{ marginTop: 'var(--space-md)' }}>
            <Field label="Latitude" id="s-lat" hint="Optional, for the map."><input id="s-lat" name="latitude" type="number" step="any" min="-90" max="90" /></Field>
            <Field label="Longitude" id="s-lng"><input id="s-lng" name="longitude" type="number" step="any" min="-180" max="180" /></Field>
            <button className="btn" type="submit">{t('Add station')}</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>{t('New account')}</h2>
        <form onSubmit={create}>
          <div className="row">
            <Field label="Name" id="n-name"><input id="n-name" name="name" required /></Field>
            <Field label="Email" id="n-email"><input id="n-email" name="email" type="email" required /></Field>
            <Field label="Password" id="n-pass"><input id="n-pass" name="password" type="password" minLength={8} required /></Field>
          </div>
          <div className="row" style={{ marginTop: 'var(--space-md)' }}>
            <Field label="Role" id="n-role">
              <select id="n-role" name="role" value={role} onChange={(e) => setRole(e.target.value)}>{data.roles.map((r) => <option key={r} value={r}>{t(r)}</option>)}</select>
            </Field>
            {role === 'officer' && (
              <>
                <Field label="Badge number" id="n-badge"><input id="n-badge" name="badge_no" required /></Field>
                <Field label="Rank" id="n-rank"><input id="n-rank" name="rank" required /></Field>
                <Field label="Station" id="n-station"><select id="n-station" name="station_id">{data.stations.map((s) => <option key={s.station_id} value={s.station_id}>{s.name}</option>)}</select></Field>
              </>
            )}
          </div>
          <button className="btn btn--primary" type="submit" style={{ marginTop: 'var(--space-md)' }}>{t('Create account')}</button>
        </form>
      </section>
    </>
  );
}

export function Audit() {
  const t = useT();
  const [params] = useSearchParams();
  const query = { entity: params.get('entity') || '', q: params.get('q') || '', page: params.get('page') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/audit', query));
  return (
    <>
      <PageHead title={t('Audit log')} text="Who changed what, newest first." />
      <Filters>
        {(p) => (
          <>
            <Field label="Search" id="q"><input id="q" name="q" defaultValue={p.get('q') || ''} placeholder={t('Person or new value')} /></Field>
            <Field label="Kind" id="entity">
              <select id="entity" name="entity" defaultValue={p.get('entity') || ''}>
                <option value="">{t('All')}</option>
                {(data?.entities || []).map((e) => <option key={e} value={e}>{t(e)}</option>)}
              </select>
            </Field>
            <button className="btn" type="submit">{t('Filter')}</button>
          </>
        )}
      </Filters>
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <div className="panel">
          {data.items.length === 0 ? <Empty>{t('Nothing recorded for that filter.')}</Empty> : (
            <>
              <div className="table-wrap"><table className="data">
                <thead><tr><th>{t('When')}</th><th>{t('Kind')}</th><th className="r">{t('Id')}</th><th>{t('Change')}</th><th>{t('By')}</th></tr></thead>
                <tbody>{data.items.map((r, i) => (
                  <tr key={i}>
                    <td className="num">{r.changed_at}</td><td>{t(r.entity)}</td><td className="num r">{r.entity_id}</td>
                    <td>{r.old_status ? `${t(r.old_status)} \u2192 ${t(r.new_status)}` : t(r.new_status)}</td><td>{r.who}</td>
                  </tr>
                ))}</tbody>
              </table></div>
              <Pager page={data.page} pages={data.pages} total={data.total} />
            </>
          )}
        </div>
      )}
    </>
  );
}
