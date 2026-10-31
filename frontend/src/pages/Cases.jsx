import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api, withQuery } from '../api.js';
import { Crumbs, Empty, Failed, Field, Filters, formData, Loading, PageHead, Pager, Status, useAct, useLoad } from '../ui.jsx';
import { useSession } from '../session.jsx';

export function Dashboard() {
  const { data, error, loading, reload } = useLoad('/dashboard');
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={reload} />;
  const { counts, queue, mine_rows, unassigned } = data;

  return (
    <>
      <PageHead title="Dashboard" text="What needs attention at the station today." />
      <div className="stats">
        <div className="stat"><b>{counts.awaiting}</b><span>Complaints awaiting review</span></div>
        <div className="stat"><b>{counts.open}</b><span>Open cases</span></div>
        <div className="stat"><b>{counts.mine}</b><span>Assigned to you</span></div>
        <div className="stat"><b>{counts.closed}</b><span>Closed cases</span></div>
      </div>

      <div className="cols cols--even">
        <section className="panel">
          <div className="panel-head"><h2>Review queue</h2><Link to="/complaints?status=Filed">All filed</Link></div>
          {queue.length ? (
            <div className="table-wrap"><table className="data">
              <thead><tr><th>Complaint</th><th>Filed by</th><th>Filed on</th></tr></thead>
              <tbody>{queue.map((c) => (
                <tr key={c.complaint_id}><td><Link to={`/complaints/${c.complaint_id}`}>{c.title}</Link></td><td>{c.citizen_name}</td><td className="num">{c.date_filed}</td></tr>
              ))}</tbody>
            </table></div>
          ) : <Empty>Every filed complaint has been reviewed.</Empty>}
        </section>

        <section className="panel">
          <div className="panel-head"><h2>Your open cases</h2><Link to="/cases?mine=1">All yours</Link></div>
          {mine_rows.length ? (
            <div className="table-wrap"><table className="data">
              <thead><tr><th className="r">Case</th><th>Complaint</th><th>Status</th></tr></thead>
              <tbody>{mine_rows.map((c) => (
                <tr key={c.case_id}><td className="num r">{c.case_id}</td><td><Link to={`/cases/${c.case_id}`}>{c.title}</Link></td><td><Status value={c.status} /></td></tr>
              ))}</tbody>
            </table></div>
          ) : <Empty>No open cases are assigned to you.</Empty>}
        </section>
      </div>

      {unassigned.length > 0 && (
        <section className="panel">
          <div className="panel-head"><h2>Cases with no officer</h2></div>
          <div className="table-wrap"><table className="data">
            <thead><tr><th className="r">Case</th><th>Complaint</th><th>Station</th><th>Opened</th></tr></thead>
            <tbody>{unassigned.map((c) => (
              <tr key={c.case_id}><td className="num r">{c.case_id}</td><td><Link to={`/cases/${c.case_id}`}>{c.title}</Link></td><td>{c.station}</td><td className="num">{c.date_opened}</td></tr>
            ))}</tbody>
          </table></div>
        </section>
      )}
    </>
  );
}

export function Cases() {
  const [params] = useSearchParams();
  const query = { q: params.get('q') || '', status: params.get('status') || '', mine: params.get('mine') || '', page: params.get('page') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/cases', query));
  const filtered = query.q || query.status || query.mine;

  return (
    <>
      <PageHead title="Cases" text="Every registered case, newest first." />
      <Filters>
        {(p) => (
          <>
            <Field label="Search" id="q"><input id="q" name="q" defaultValue={p.get('q') || ''} placeholder="Title, citizen or location" /></Field>
            <Field label="Status" id="status">
              <select id="status" name="status" defaultValue={p.get('status') || ''}>
                <option value="">All</option>
                {(data?.statuses || []).map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <div className="field row-end"><label><input type="checkbox" name="mine" value="1" defaultChecked={p.get('mine') === '1'} />Only mine</label></div>
            <button className="btn" type="submit">Filter</button>
          </>
        )}
      </Filters>
      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <div className="panel">
          {data.items.length === 0 ? (
            filtered
              ? <Empty action={<Link className="btn" to="/cases">Clear filters</Link>}>No cases match those filters.</Empty>
              : <Empty action={<Link className="btn" to="/complaints?status=Filed">Filed complaints</Link>}>No cases yet. Verify a complaint, then register it as a case.</Empty>
          ) : (
            <>
              <div className="table-wrap"><table className="data">
                <thead><tr><th className="r">Case</th><th>Complaint</th><th>Station</th><th>Officer</th><th>Opened</th><th>Status</th></tr></thead>
                <tbody>{data.items.map((c) => (
                  <tr key={c.case_id}>
                    <td className="num r">{c.case_id}</td>
                    <td><Link to={`/cases/${c.case_id}`}>{c.title}</Link><div className="muted">{c.citizen_name}</div></td>
                    <td>{c.station}</td><td>{c.officer_name || 'Unassigned'}</td>
                    <td className="num">{c.date_opened}</td><td><Status value={c.status} /></td>
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

export function Case() {
  const { id } = useParams();
  const { user } = useSession();
  const { data, error, loading, reload } = useLoad(`/cases/${id}`);
  const act = useAct(reload);
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={error.status === 404 ? undefined : reload} />;

  const { case: c, evidence, linked, available, reports, notes, history, officers, editable, next_states } = data;
  const send = (path, body, ok, method = 'POST') => act(() => api(`/cases/${id}${path}`, { method, body }), ok);
  // reset the form once the write has gone through
  const submit = (path, ok, shape = (b) => b) => async (event) => {
    const body = shape(formData(event));
    const form = event.target;
    await send(path, body, ok);
    form.reset();
  };

  return (
    <>
      <Crumbs trail={[['Cases', '/cases']]} here={`Case ${c.case_id}`} />
      <PageHead title={c.title} text={`Opened ${c.date_opened} at ${c.station}`}><Status value={c.status} /></PageHead>
      {!editable && (
        <div className="flash">
          {c.status.startsWith('Closed') ? 'This case is closed and read-only.' : 'Only the assigned officer or an admin can change this case.'}
        </div>
      )}

      <div className="cols">
        <div>
          <section className="panel">
            <h2>Complaint</h2>
            <dl className="facts">
              <dt>Filed by</dt><dd>{c.citizen_name}</dd>
              <dt>Where</dt><dd>{c.location}</dd>
              <dt>Incident date</dt><dd className="num">{c.incident_date}</dd>
              <dt>Description</dt><dd className="prose">{c.description}</dd>
            </dl>
            {notes.map((n, i) => (
              <div className="note" key={i}><small>Citizen {n.kind}, {n.created_at}</small><div className="prose">{n.body}</div></div>
            ))}
            <p style={{ marginTop: 'var(--space-md)' }}><Link to={`/complaints/${c.complaint_id}`}>Open the original complaint</Link></p>
          </section>

          <section className="panel">
            <h2>Evidence</h2>
            {evidence.length ? (
              <div className="table-wrap"><table className="data">
                <thead><tr><th className="r">No.</th><th>Type</th><th>Description</th><th>Collected</th></tr></thead>
                <tbody>{evidence.map((e) => (
                  <tr key={e.evidence_no}><td className="num r">{e.evidence_no}</td><td>{e.type}</td><td className="prose">{e.description}</td><td className="num">{e.date_collected}</td></tr>
                ))}</tbody>
              </table></div>
            ) : <p className="muted">No evidence recorded.</p>}
            {editable && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>Record evidence</summary>
                <form onSubmit={submit('/evidence', 'Evidence recorded.')}>
                  <Field label="Type" id="type"><input id="type" name="type" placeholder="Photograph, CCTV, weapon" required /></Field>
                  <Field label="Description" id="ev-desc"><textarea id="ev-desc" name="description" required /></Field>
                  <button className="btn" type="submit">Save evidence</button>
                </form>
              </details>
            )}
          </section>

          <section className="panel">
            <h2>People linked to the case</h2>
            {linked.length ? (
              <div className="table-wrap"><table className="data">
                <thead><tr><th>Name</th><th>Role</th><th className="r">Age</th><th></th></tr></thead>
                <tbody>{linked.map((p) => (
                  <tr key={p.criminal_id}>
                    <td><Link to={`/criminals/${p.criminal_id}`}>{p.name}</Link></td>
                    <td style={{ textTransform: 'capitalize' }}>{p.role}</td>
                    <td className="num r">{p.age}</td>
                    <td>{editable && <button className="link-btn" onClick={() => send(`/criminals/${p.criminal_id}`, undefined, 'Removed from the case.', 'DELETE')}>Remove</button>}</td>
                  </tr>
                ))}</tbody>
              </table></div>
            ) : <p className="muted">Nobody is linked yet.</p>}
            {editable && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>Link a criminal record</summary>
                {available.length ? (
                  <form onSubmit={submit('/criminals', 'Linked to the case.', (b) => ({ ...b, criminal_id: Number(b.criminal_id) }))}>
                    <div className="row">
                      <Field label="Person" id="criminal_id"><select id="criminal_id" name="criminal_id">{available.map((a) => <option key={a.criminal_id} value={a.criminal_id}>{a.name}</option>)}</select></Field>
                      <Field label="Role" id="role"><select id="role" name="role"><option>suspect</option><option>accused</option><option>witness</option><option>victim</option></select></Field>
                      <button className="btn" type="submit">Link</button>
                    </div>
                  </form>
                ) : <p className="muted">Every record is already linked. <Link to="/criminals/new">Add a new record</Link>.</p>}
              </details>
            )}
          </section>

          <section className="panel">
            <h2>Reports</h2>
            {reports.length === 0 && <p className="muted">No reports written.</p>}
            {reports.map((r) => (
              <div className="note" key={r.report_id}><small>{r.date_generated}{r.author && `, ${r.author}`}</small><div className="prose">{r.content}</div></div>
            ))}
            {editable && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>Write a report</summary>
                <form onSubmit={submit('/reports', 'Report saved.')}>
                  <Field label="Report" id="content"><textarea id="content" name="content" required /></Field>
                  <button className="btn" type="submit">Save report</button>
                </form>
              </details>
            )}
          </section>
        </div>

        <div>
          <section className="panel">
            <h2>Status</h2>
            <dl className="facts">
              <dt>Current</dt><dd><Status value={c.status} /></dd>
              <dt>Officer</dt><dd>{c.officer_name || 'Unassigned'}</dd>
            </dl>
            {editable && next_states.length > 0 && (
              <form onSubmit={submit('/status', 'Case status updated.')} style={{ marginTop: 'var(--space-md)' }}>
                <Field label="Move to" id="status"><select id="status" name="status">{next_states.map((s) => <option key={s}>{s}</option>)}</select></Field>
                <button className="btn btn--primary" type="submit">Update status</button>
              </form>
            )}
          </section>

          {user.role === 'admin' && !c.status.startsWith('Closed') && (
            <section className="panel">
              <h2>Assign officer</h2>
              <form onSubmit={submit('/assign', 'Officer assigned.', (b) => ({ officer_id: Number(b.officer_id) }))}>
                <Field label="Officer" id="officer_id">
                  <select id="officer_id" name="officer_id" defaultValue={officers.find((o) => o.name === c.officer_name)?.officer_id}>
                    {officers.map((o) => <option key={o.officer_id} value={o.officer_id}>{o.name}, {o.rank}</option>)}
                  </select>
                </Field>
                <button className="btn" type="submit">Assign</button>
              </form>
            </section>
          )}

          <section className="panel">
            <h2>Status history</h2>
            <ul className="trail">
              {history.map((h, i) => (
                <li key={i}><span>{h.new_status}{h.who && <span className="muted"> by {h.who}</span>}</span><span className="num muted">{h.changed_at.slice(0, 10)}</span></li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
