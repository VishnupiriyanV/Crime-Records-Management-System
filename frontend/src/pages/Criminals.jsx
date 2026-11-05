import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, withQuery } from '../api.js';
import { useSession } from '../session.jsx';
import { Crumbs, Download, Empty, Failed, Field, Filters, formData, Loading, PageHead, Pager, SortTh, Status, useAct, useLoad } from '../ui.jsx';

export function Criminals() {
  const [params] = useSearchParams();
  const query = { q: params.get('q') || '', wanted: params.get('wanted') || '', page: params.get('page') || '', sort: params.get('sort') || '', dir: params.get('dir') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/criminals', query));

  return (
    <>
      <PageHead title="Criminal records" text="Search by name or history; open a record to see its cases.">
        <div className="head-actions">
          <Download path="/export/criminals.csv" params={params}>Export CSV</Download>
          <Link className="btn btn--primary" to="/criminals/new">Add record</Link>
        </div>
      </PageHead>
      <Filters>
        {(p) => (
          <>
            <Field label="Search" id="q"><input id="q" name="q" defaultValue={p.get('q') || ''} placeholder="Name or history" /></Field>
            <div className="field row-end"><label><input type="checkbox" name="wanted" value="1" defaultChecked={p.get('wanted') === '1'} />Wanted only</label></div>
            <button className="btn" type="submit">Search</button>
          </>
        )}
      </Filters>
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <div className="panel">
          {data.items.length === 0 ? (
            query.q || query.wanted
              ? <Empty action={<Link className="btn" to="/criminals">Clear search</Link>}>No records match that search.</Empty>
              : <Empty action={<Link className="btn btn--primary" to="/criminals/new">Add the first record</Link>}>No criminal records yet.</Empty>
          ) : (
            <>
              <div className="table-wrap"><table className="data">
                <thead><tr><SortTh id="name">Name</SortTh><SortTh id="age" className="r">Age</SortTh><th>History</th><SortTh id="cases" className="r">Cases</SortTh><SortTh id="wanted">Wanted</SortTh></tr></thead>
                <tbody>{data.items.map((c) => (
                  <tr key={c.criminal_id}>
                    <td><Link to={`/criminals/${c.criminal_id}`}>{c.name}</Link></td>
                    <td className="num r">{c.age}</td><td>{c.crime_history}</td>
                    <td className="num r">{c.cases}</td>
                    <td>{c.wanted ? <span className="badge badge--bad">Wanted</span> : null}</td>
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

export function CriminalForm() {
  const { id } = useParams();
  const isNew = !id;
  const navigate = useNavigate();
  const { notice } = useSession();
  const { data, error, loading, reload } = useLoad(isNew ? '/auth/me' : `/criminals/${id}`);
  const act = useAct();
  if (!isNew && loading) return <Loading />;
  if (!isNew && error) return <Failed error={error} retry={error.status === 404 ? undefined : reload} />;

  const c = isNew ? {} : data.criminal;
  const cases = isNew ? [] : data.cases;

  const save = (event) => {
    const form = formData(event);
    const body = { ...form, wanted: form.wanted === 'on' };
    return act(async () => {
      if (isNew) {
        const { criminal_id } = await api('/criminals', { method: 'POST', body });
        notice('Record added.', 'ok', true);
        navigate(`/criminals/${criminal_id}`);
      } else {
        await api(`/criminals/${id}`, { method: 'PUT', body });
        notice('Record updated.', 'ok');
        reload();
      }
    });
  };

  return (
    <>
      <Crumbs trail={[['Criminal records', '/criminals']]} here={isNew ? 'New' : c.name} />
      <PageHead title={isNew ? 'Add criminal record' : c.name} />
      <div className={isNew ? '' : 'cols'}>
        <form className={`panel ${isNew ? 'form-narrow' : ''}`} onSubmit={save}>
          <Field label="Name" id="name"><input id="name" name="name" defaultValue={c.name || ''} required /></Field>
          <Field label="Age" id="age"><input id="age" name="age" type="number" min="0" max="120" defaultValue={c.age ?? ''} /></Field>
          <Field label="Crime history" id="crime_history"><textarea id="crime_history" name="crime_history" defaultValue={c.crime_history || ''} /></Field>
          <div className="field"><label><input type="checkbox" name="wanted" defaultChecked={!!c.wanted} />Listed as wanted (visible in public records)</label></div>
          <button className="btn btn--primary" type="submit">{isNew ? 'Add record' : 'Save changes'}</button>
        </form>
        {!isNew && (
          <section className="panel">
            <h2>Cases</h2>
            {cases.length ? (
              <ul className="trail">{cases.map((k) => (
                <li key={k.case_id}><span><Link to={`/cases/${k.case_id}`}>{k.title}</Link> <span className="muted">{k.role}</span></span><Status value={k.status} /></li>
              ))}</ul>
            ) : <p className="muted">Not linked to any case.</p>}
          </section>
        )}
      </div>
    </>
  );
}
