import { Link, useParams } from 'react-router-dom';
import { api, upload } from '../api.js';
import { Bars } from '../charts.jsx';
import { Avatar, Crumbs, Empty, Failed, Field, formData, Loading, PageHead, Status, Tags, useAct, useLoad } from '../ui.jsx';
import { useT } from '../i18n.jsx';

export function Stations() {
  const t = useT();
  const { data, error, loading, reload } = useLoad('/stations');
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={reload} />;
  return (
    <>
      <PageHead title={t('Stations')} text="Every station with its officers and open work." />
      <div className="panel">
        {data.items.length === 0 ? <Empty>{t('No stations yet.')}</Empty> : (
          <div className="table-wrap"><table className="data">
            <thead><tr><th>{t('Station')}</th><th>{t('Area covered')}</th><th>{t('Phone')}</th><th className="r">{t('Officers')}</th><th className="r">{t('Open cases')}</th><th className="r">{t('All cases')}</th></tr></thead>
            <tbody>{data.items.map((s) => (
              <tr key={s.station_id}>
                <td><Link to={`/stations/${s.station_id}`}>{s.name}</Link></td><td>{s.jurisdiction}</td><td className="num">{s.phone}</td>
                <td className="num r">{s.officers}</td><td className="num r">{s.open_cases}</td><td className="num r">{s.cases}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </>
  );
}

export function Station() {
  const t = useT();
  const { id } = useParams();
  const { data, error, loading, reload } = useLoad(`/stations/${id}`);
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={error.status === 404 ? undefined : reload} />;
  const { station, by_status, by_category, officers, recent, unassigned } = data;
  const open = by_status.filter((r) => !r.status.startsWith('Closed')).reduce((n, r) => n + r.total, 0);
  const total = by_status.reduce((n, r) => n + r.total, 0);

  return (
    <>
      <Crumbs trail={[['Stations', '/stations']]} here={station.name} />
      <PageHead title={station.name} text={`${station.jurisdiction}${station.phone ? `, ${station.phone}` : ''}`} />
      <div className="stats stats--three stats--loose">
        <div className="stat"><b>{total}</b><span>{t('Cases')}</span></div>
        <div className="stat"><b>{open}</b><span>{t('Open')}</span></div>
        <div className="stat"><b>{unassigned}</b><span>{t('Open with no officer')}</span></div>
      </div>

      <section className="panel">
        <h2>{t('Officers')}</h2>
        {officers.length === 0 ? <Empty>{t('No officers are posted here.')}</Empty> : (
          <div className="people">
            {officers.map((o) => (
              <Link className="person" key={o.officer_id} to={`/officers/${o.officer_id}`}>
                <Avatar officerId={o.officer_id} name={o.name} has={o.has_photo} />
                <span>
                  <b>{o.name}</b>
                  <span className="muted">{t('{rank}, badge {badge}', { rank: o.officer_rank, badge: o.badge_no })}</span>
                  <span className="num">{t('{open} open, {resolved} resolved', { open: o.open, resolved: o.resolved })}</span>
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>

      <div className="cols cols--even">
        <section className="panel">
          <h2>{t('Cases by status')}</h2>
          {by_status.length ? <Bars rows={by_status} label="status" value="total" title={t('Cases by status')} /> : <Empty>{t('No cases yet.')}</Empty>}
        </section>
        <section className="panel">
          <h2>{t('Cases by category')}</h2>
          {by_category.length ? <Bars rows={by_category} label="category" value="total" title={t('Cases by category')} /> : <Empty>{t('No cases yet.')}</Empty>}
        </section>
      </div>

      <section className="panel">
        <h2>{t('Recent cases')}</h2>
        {recent.length ? (
          <div className="table-wrap"><table className="data">
            <thead><tr><th className="r">{t('Case')}</th><th>{t('Complaint')}</th><th>{t('Category')}</th><th>{t('Officer')}</th><th>{t('Opened')}</th><th>{t('Status')}</th></tr></thead>
            <tbody>{recent.map((c) => (
              <tr key={c.case_id}>
                <td className="num r">{c.case_id}</td><td><Link to={`/cases/${c.case_id}`}>{c.title}</Link></td>
                <td><Tags category={c.category} severity={c.severity} /></td><td>{c.officer_name || t('Unassigned')}</td>
                <td className="num">{c.date_opened}</td><td><Status value={c.status} /></td>
              </tr>
            ))}</tbody>
          </table></div>
        ) : <Empty>{t('No cases yet.')}</Empty>}
      </section>
    </>
  );
}

export function Officer() {
  const t = useT();
  const { id } = useParams();
  const { data, error, loading, reload } = useLoad(`/officers/${id}`);
  const act = useAct(reload);
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={error.status === 404 ? undefined : reload} />;
  const { officer: o, open_cases, closed_cases, can_edit_photo } = data;

  const changePhoto = async (event) => {
    const { file } = formData(event);
    const form = event.target;
    if (!file || !file.size) return;
    const done = await act(() => upload(`/officers/${id}/photo`, file), 'Photo updated.');
    if (done) form.reset();
  };

  return (
    <>
      <Crumbs trail={[['Stations', '/stations'], [o.station, `/stations/${o.station_id}`]]} here={o.name} />
      <div className="officer-head">
        <Avatar key={o.has_photo} officerId={o.officer_id} name={o.name} has={o.has_photo} size={96} />
        <div>
          <h1>{o.name}</h1>
          <p className="muted">{t('{rank}, badge {badge}, {station}', { rank: o.officer_rank, badge: o.badge_no, station: o.station })}</p>
          {!o.active && <span className="badge badge--bad">{t('Inactive')}</span>}
        </div>
      </div>

      <div className="stats stats--three stats--loose">
        <div className="stat"><b>{o.open}</b><span>{t('Open cases')}</span></div>
        <div className="stat"><b>{o.resolved}</b><span>{t('Resolved')}</span></div>
        <div className="stat"><b>{o.resolution_rate == null ? '-' : `${o.resolution_rate}%`}</b><span>{t('Of closed cases resolved')}</span></div>
      </div>

      <div className="cols">
        <div>
          <section className="panel">
            <h2>{t('Open cases')}</h2>
            {open_cases.length ? (
              <div className="table-wrap"><table className="data">
                <thead><tr><th className="r">{t('Case')}</th><th>{t('Complaint')}</th><th>{t('Category')}</th><th>{t('Status')}</th></tr></thead>
                <tbody>{open_cases.map((c) => (
                  <tr key={c.case_id}><td className="num r">{c.case_id}</td><td><Link to={`/cases/${c.case_id}`}>{c.title}</Link></td><td><Tags category={c.category} severity={c.severity} /></td><td><Status value={c.status} /></td></tr>
                ))}</tbody>
              </table></div>
            ) : <Empty>{t('No open cases.')}</Empty>}
          </section>
          <section className="panel">
            <h2>{t('Recently closed')}</h2>
            {closed_cases.length ? (
              <ul className="trail">{closed_cases.map((c) => (
                <li key={c.case_id}><span><Link to={`/cases/${c.case_id}`}>{c.title}</Link></span><Status value={c.status} /></li>
              ))}</ul>
            ) : <p className="muted">{t('Nothing closed yet.')}</p>}
          </section>
        </div>
        <div>
          <section className="panel">
            <h2>{t('Contact')}</h2>
            <dl className="facts"><dt>{t('Email')}</dt><dd>{o.email}</dd><dt>{t('Station')}</dt><dd><Link to={`/stations/${o.station_id}`}>{o.station}</Link></dd></dl>
          </section>
          {can_edit_photo && (
            <section className="panel">
              <h2>{t('Photo')}</h2>
              <form onSubmit={changePhoto}>
                <Field label="Choose an image" id="photo" hint="JPG, PNG or WebP, up to 1 MB.">
                  <input id="photo" name="file" type="file" accept=".jpg,.jpeg,.png,.webp" required />
                </Field>
                <button className="btn" type="submit">{t('Upload')}</button>
              </form>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
