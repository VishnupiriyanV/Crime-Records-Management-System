import { Link, useSearchParams } from 'react-router-dom';
import { withQuery } from '../api.js';
import { Empty, Failed, Loading, PageHead, Status, useLoad } from '../ui.jsx';

export function Search() {
  const [params] = useSearchParams();
  const q = (params.get('q') || '').trim();
  const { data, error, loading, reload } = useLoad(withQuery('/search', { q }));

  const none = data && !data.complaints.length && !data.cases.length && !data.criminals.length;
  return (
    <>
      <PageHead title="Search" text={q ? `Results for “${q}”.` : 'Type at least two letters in the search box.'} />
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : none ? (
        <div className="panel"><Empty>{q.length < 2 ? 'Nothing to search for yet.' : 'Nothing matches that.'}</Empty></div>
      ) : (
        <>
          {data.complaints.length > 0 && (
            <section className="panel">
              <h2>Complaints</h2>
              <ul className="trail">
                {data.complaints.map((c) => (
                  <li key={c.complaint_id}>
                    <span><Link to={`/complaints/${c.complaint_id}`}>{c.title}</Link> <span className="muted">{c.fir_no}, {c.location}</span></span>
                    <Status value={c.status} />
                  </li>
                ))}
              </ul>
            </section>
          )}
          {data.cases.length > 0 && (
            <section className="panel">
              <h2>Cases</h2>
              <ul className="trail">
                {data.cases.map((c) => (
                  <li key={c.case_id}>
                    <span><Link to={`/cases/${c.case_id}`}>Case {c.case_id}: {c.title}</Link> <span className="muted">{c.location}</span></span>
                    <Status value={c.status} />
                  </li>
                ))}
              </ul>
            </section>
          )}
          {data.criminals.length > 0 && (
            <section className="panel">
              <h2>Criminal records</h2>
              <ul className="trail">
                {data.criminals.map((c) => (
                  <li key={c.criminal_id}>
                    <Link to={`/criminals/${c.criminal_id}`}>{c.name}</Link>
                    {c.wanted ? <span className="badge badge--bad">Wanted</span> : null}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </>
  );
}
