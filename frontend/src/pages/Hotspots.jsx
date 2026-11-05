import { Link, useSearchParams } from 'react-router-dom';
import { withQuery } from '../api.js';
import { HotspotMap, severityColor } from '../MapView.jsx';
import { Empty, Failed, Field, Filters, Loading, PageHead, useLoad } from '../ui.jsx';

export function Hotspots() {
  const [params] = useSearchParams();
  const query = { category: params.get('category') || '', severity: params.get('severity') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/map', query));

  return (
    <>
      <PageHead title="Map" text="Where complaints are coming from. Larger rings are the busiest areas." />
      <Filters>
        {(p) => (
          <>
            <Field label="Category" id="category">
              <select id="category" name="category" defaultValue={p.get('category') || ''}>
                <option value="">All</option>
                {(data?.categories || []).map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Severity" id="severity">
              <select id="severity" name="severity" defaultValue={p.get('severity') || ''}>
                <option value="">All</option>
                {(data?.severities || []).map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <button className="btn" type="submit">Filter</button>
          </>
        )}
      </Filters>
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <>
          <section className="panel">
            <HotspotMap points={data.points} hotspots={data.hotspots} stations={data.stations} />
            <p className="legend">
              {['High', 'Medium', 'Low'].map((s) => <span key={s}><i style={{ background: severityColor(s) }} /> {s}</span>)}
              <span><i className="legend-station" /> Station</span>
              <span className="muted">{data.points.length} complaints with a pin</span>
            </p>
          </section>
          <section className="panel">
            <h2>Busiest areas</h2>
            {data.hotspots.length === 0 ? <Empty>No complaints have a map pin yet.</Empty> : (
              <div className="table-wrap"><table className="data">
                <thead><tr><th className="r">Complaints</th><th>Mostly</th><th className="r">High severity</th><th>Nearest station</th><th>Around</th></tr></thead>
                <tbody>{data.hotspots.map((h) => (
                  <tr key={`${h.latitude},${h.longitude}`}>
                    <td className="num r">{h.total}</td><td>{h.top_category}</td><td className="num r">{h.high}</td>
                    <td>{h.station || '-'}</td><td className="num">{h.latitude.toFixed(2)}, {h.longitude.toFixed(2)}</td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
            <p className="muted" style={{ marginTop: 'var(--space-sm)' }}>Areas are grouped into cells of about one kilometre. <Link to="/complaints">See all complaints</Link>.</p>
          </section>
        </>
      )}
    </>
  );
}
