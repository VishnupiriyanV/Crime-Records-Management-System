import { Link, useSearchParams } from 'react-router-dom';
import { withQuery } from '../api.js';
import { HotspotMap, severityColor } from '../MapView.jsx';
import { Empty, Failed, Field, Filters, Loading, PageHead, useLoad } from '../ui.jsx';
import { useT } from '../i18n.jsx';

export function Hotspots() {
  const t = useT();
  const [params] = useSearchParams();
  const query = { category: params.get('category') || '', severity: params.get('severity') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/map', query));

  return (
    <>
      <PageHead title={t('Map')} text="Where complaints are coming from. Larger rings are the busiest areas." />
      <Filters>
        {(p) => (
          <>
            <Field label="Category" id="category">
              <select id="category" name="category" defaultValue={p.get('category') || ''}>
                <option value="">{t('All')}</option>
                {(data?.categories || []).map((c) => <option key={c} value={c}>{t(c)}</option>)}
              </select>
            </Field>
            <Field label="Severity" id="severity">
              <select id="severity" name="severity" defaultValue={p.get('severity') || ''}>
                <option value="">{t('All')}</option>
                {(data?.severities || []).map((c) => <option key={c} value={c}>{t(c)}</option>)}
              </select>
            </Field>
            <button className="btn" type="submit">{t('Filter')}</button>
          </>
        )}
      </Filters>
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <>
          <section className="panel">
            <HotspotMap points={data.points} hotspots={data.hotspots} stations={data.stations} />
            <p className="legend">
              {['High', 'Medium', 'Low'].map((s) => <span key={s}><i style={{ background: severityColor(s) }} /> {t(s)}</span>)}
              <span><i className="legend-station" />{' '}{t('Station')}</span>
              <span className="muted">{t('{n} complaints with a pin', { n: data.points.length })}</span>
            </p>
          </section>
          <section className="panel">
            <h2>{t('Busiest areas')}</h2>
            {data.hotspots.length === 0 ? <Empty>{t('No complaints have a map pin yet.')}</Empty> : (
              <div className="table-wrap"><table className="data">
                <thead><tr><th className="r">{t('Complaints')}</th><th>{t('Mostly')}</th><th className="r">{t('High severity')}</th><th>{t('Nearest station')}</th><th>{t('Around')}</th></tr></thead>
                <tbody>{data.hotspots.map((h) => (
                  <tr key={`${h.latitude},${h.longitude}`}>
                    <td className="num r">{h.total}</td><td>{t(h.top_category)}</td><td className="num r">{h.high}</td>
                    <td>{h.station || '-'}</td><td className="num">{h.latitude.toFixed(2)}, {h.longitude.toFixed(2)}</td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
            <p className="muted" style={{ marginTop: 'var(--space-sm)' }}>{t('Areas are grouped into cells of about one kilometre.')}{' '}<Link to="/complaints">{t('See all complaints')}</Link>.</p>
          </section>
        </>
      )}
    </>
  );
}
