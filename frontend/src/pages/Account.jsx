import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, withQuery } from '../api.js';
import { useSession } from '../session.jsx';
import { Empty, Failed, Field, Filters, formData, Loading, PageHead, useAct, useLoad } from '../ui.jsx';
import { useT } from '../i18n.jsx';

export function Profile() {
  const t = useT();
  const { user, setSession } = useSession();
  const { data, error, loading, reload } = useLoad('/profile');
  const act = useAct();
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={reload} />;

  const save = (event) => {
    const form = event.target;
    const body = formData(event);
    if (form.elements.email_alerts) body.email_alerts = form.elements.email_alerts.checked;
    return act(async () => setSession(await api('/profile', { method: 'PUT', body })), 'Profile saved.');
  };
  return (
    <>
      <PageHead title="Profile" text={t('{email}, signed in as {role}.', { email: user.email, role: t(user.role) })} />
      <form className="panel form-narrow" onSubmit={save}>
        <Field label="Full name" id="name"><input id="name" name="name" defaultValue={user.name} required /></Field>
        {data.extra && (
          <>
            <Field label="Address" id="address"><input id="address" name="address" defaultValue={data.extra.address || ''} /></Field>
            <Field label="Phone" id="phone"><input id="phone" name="phone" defaultValue={data.extra.phone || ''} /></Field>
          </>
        )}
        <Field label="New password" id="password" hint="Leave blank to keep the current one.">
          <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} />
        </Field>
        <Field label="Current password" id="current_password" hint="Only needed when you set a new password.">
          <input id="current_password" name="current_password" type="password" autoComplete="current-password" />
        </Field>
        {data.email_possible && (
          <div className="field">
            <label><input type="checkbox" name="email_alerts" defaultChecked={data.email_alerts} />{t('E-mail me when something changes on my complaints and cases')}</label>
          </div>
        )}
        <button className="btn btn--primary" type="submit">{t('Save changes')}</button>
      </form>
    </>
  );
}

export function Notifications() {
  const t = useT();
  const { data, error, loading, reload } = useLoad('/notifications');
  const { refresh } = useSession();
  // opening the page marks everything as read on the server, so refresh the bell count
  useEffect(() => { if (data) refresh(); }, [data, refresh]);
  return (
    <>
      <PageHead title="Alerts" text="Updates on your complaints and cases." />
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <div className="panel">
          {data.items.length === 0 ? <Empty>Nothing yet. You will be told here when a complaint or case changes.</Empty> : (
            <ul className="trail">
              {data.items.map((n, i) => (
                <li key={i}>
                  <span>{n.link ? <Link to={n.link}>{t(n.message)}</Link> : t(n.message)}</span>
                  <span className="num muted">{n.created_at}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
}

export function Records() {
  const t = useT();
  const [params] = useSearchParams();
  const { data, error, loading, reload } = useLoad(withQuery('/records', { q: params.get('q') || '' }));
  return (
    <>
      <PageHead title="Public records" text="Wanted persons and station contacts. Case files are not public." />
      <Filters>
        {(p) => (
          <>
            <Field label="Search" id="q"><input id="q" name="q" defaultValue={p.get('q') || ''} placeholder={t('Name or area')} /></Field>
            <button className="btn" type="submit">{t('Search')}</button>
          </>
        )}
      </Filters>
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <div className="cols cols--even">
          <section className="panel">
            <h2>{t('Wanted persons')}</h2>
            {data.wanted.length ? (
              <div className="table-wrap"><table className="data">
                <thead><tr><th>{t('Name')}</th><th className="r">{t('Age')}</th></tr></thead>
                <tbody>{data.wanted.map((w) => <tr key={w.name}><td>{w.name}</td><td className="num r">{w.age}</td></tr>)}</tbody>
              </table></div>
            ) : <Empty>No wanted persons match.</Empty>}
          </section>
          <section className="panel">
            <h2>{t('Police stations')}</h2>
            {data.stations.length ? (
              <div className="table-wrap"><table className="data">
                <thead><tr><th>{t('Station')}</th><th>{t('Area covered')}</th></tr></thead>
                <tbody>{data.stations.map((s) => <tr key={s.station_id}><td>{s.name}</td><td>{s.jurisdiction}</td></tr>)}</tbody>
              </table></div>
            ) : <Empty>No stations match.</Empty>}
          </section>
        </div>
      )}
    </>
  );
}
