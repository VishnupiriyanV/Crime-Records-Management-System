import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api, upload, withQuery } from '../api.js';
import { Bars, Line } from '../charts.jsx';
import { Attachments, Crumbs, Download, Empty, Failed, Field, Filters, Flags, formData, Loading, PageHead, Pager, SortTh, Status, Tags, Timeline, useAct, useLoad } from '../ui.jsx';
import { useSession } from '../session.jsx';
import { Dictate } from '../voice.jsx';

const WAITING = {
  unreviewed: 'Complaints waiting for review', unassigned: 'Cases with no officer',
  stale: 'Cases with no recent activity', hearing: 'Hearings with no outcome',
};

// loads on its own so the rest of the dashboard does not wait for it
function Attention() {
  const { data, error } = useLoad('/attention');
  if (error) return null;
  if (!data) return <section className="panel"><h2>Needs attention</h2><div className="skeleton" /></section>;
  const { counts, items, limits } = data;
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return (
    <section className="panel">
      <h2>Needs attention</h2>
      {total === 0 ? <Empty>Nothing has waited too long.</Empty> : (
        <>
          <div className="stats">
            {Object.entries(WAITING).map(([kind, label]) => (
              <div className="stat" key={kind}><b>{counts[kind]}</b><span>{label}</span></div>
            ))}
          </div>
          <ul className="trail">
            {items.map((i, n) => (
              <li key={n}><span><Link to={i.link}>{i.fir} {i.title}</Link></span><span className="muted">{i.text}</span></li>
            ))}
          </ul>
        </>
      )}
      <p className="muted" style={{ marginTop: 'var(--space-sm)' }}>
        Flags appear after {limits.unreviewed} days unreviewed, {limits.unassigned} days with no officer and {limits.stale} days with no activity. High severity waits half as long.
      </p>
    </section>
  );
}

export function Dashboard() {
  const { data, error, loading, reload } = useLoad('/dashboard');
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={reload} />;
  const { counts, queue, mine_rows, unassigned, by_status, by_category, monthly, hearings } = data;

  return (
    <>
      <PageHead title="Dashboard" text="What needs attention at the station today." />
      <div className="stats">
        <div className="stat"><b>{counts.awaiting}</b><span>Complaints awaiting review</span></div>
        <div className="stat"><b>{counts.open}</b><span>Open cases</span></div>
        <div className="stat"><b>{counts.mine}</b><span>Assigned to you</span></div>
        <div className="stat"><b>{counts.closed}</b><span>Closed cases</span></div>
      </div>

      <Attention />

      <div className="cols cols--even">
        <section className="panel">
          <h2>Cases by status</h2>
          {by_status.length ? <Bars rows={by_status} label="status" value="total" title="Cases by status" /> : <Empty>No cases registered yet.</Empty>}
        </section>
        <section className="panel">
          <h2>Complaints filed, last 12 months</h2>
          <Line points={monthly} title="Complaints filed per month" />
        </section>
      </div>

      <div className="cols cols--even">
        <section className="panel">
          <h2>Complaints by category</h2>
          {by_category.length ? <Bars rows={by_category} label="category" value="total" title="Complaints by category" /> : <Empty>No complaints yet.</Empty>}
        </section>
        <section className="panel">
          <h2>Upcoming court dates</h2>
          {hearings.length ? (
            <ul className="trail">
              {hearings.map((h) => (
                <li key={`${h.case_id}-${h.no}`}>
                  <span><Link to={`/cases/${h.case_id}`}>{h.title}</Link><span className="muted"> {h.court}, {h.purpose}</span></span>
                  <span className="num">{h.date}</span>
                </li>
              ))}
            </ul>
          ) : <Empty>No hearings are scheduled.</Empty>}
        </section>
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
  const query = { q: params.get('q') || '', status: params.get('status') || '', mine: params.get('mine') || '', category: params.get('category') || '', page: params.get('page') || '', sort: params.get('sort') || '', dir: params.get('dir') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/cases', query));
  const filtered = query.q || query.status || query.mine || query.category;

  return (
    <>
      <PageHead title="Cases" text="Every registered case, newest first."><Download path="/export/cases.csv" params={params}>Export CSV</Download></PageHead>
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
            <Field label="Category" id="category">
              <select id="category" name="category" defaultValue={p.get('category') || ''}>
                <option value="">All</option>
                {(data?.categories || []).map((c) => <option key={c}>{c}</option>)}
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
                <thead><tr><SortTh id="no" className="r">Case</SortTh><SortTh id="title">Complaint</SortTh><th>Category</th><SortTh id="station">Station</SortTh><SortTh id="officer">Officer</SortTh><SortTh id="opened">Opened</SortTh><SortTh id="status">Status</SortTh></tr></thead>
                <tbody>{data.items.map((c) => (
                  <tr key={c.case_id}>
                    <td className="num r">{c.case_id}</td>
                    <td><Link to={`/cases/${c.case_id}`}>{c.title}</Link><div className="muted">{c.fir_no}, {c.citizen_name}</div><Flags items={c.flags} /></td>
                    <td><Tags category={c.category} severity={c.severity} /></td>
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

  const { case: c, evidence, linked, available, reports, notes, timeline, attachments, officers, editable, next_states, statements, arrests, court_dates, chargesheet, custody_actions, flags } = data;
  const send = (path, body, ok, method = 'POST') => act(() => api(`/cases/${id}${path}`, { method, body }), ok);
  // reset the form once the write has gone through
  const sendFile = (no) => async (event) => {
    const { file } = formData(event);
    const form = event.target;
    if (!file || !file.size) return;
    const done = await act(() => upload(`/cases/${id}/evidence/${no}/files`, file), 'File added.');
    if (done) form.reset();
  };
  // the item is saved first, then the file is added to it; a rejected file should not lose the item
  const recordEvidence = async (event) => {
    const { file, ...body } = formData(event);
    const form = event.target;
    const made = await act(() => api(`/cases/${id}/evidence`, { method: 'POST', body }), 'Evidence recorded.');
    if (!made) return;
    if (file && file.size) {
      await act(() => upload(`/cases/${id}/evidence/${made.evidence_no}/files`, file), 'File added.');
    }
    form.reset();
  };
  // a charge sheet is filed on its own form, so the plain status list leaves it out
  const manualStates = next_states.filter((x) => x !== 'Chargesheet Filed');
  const chargeable = linked.filter((p) => p.role === 'suspect' || p.role === 'accused');
  const submit = (path, ok, shape = (b) => b) => async (event) => {
    const body = shape(formData(event));
    const form = event.target;
    await send(path, body, ok);
    form.reset();
  };

  return (
    <>
      <Crumbs trail={[['Cases', '/cases']]} here={`Case ${c.case_id}`} />
      <PageHead title={c.title} text={`${c.fir_no}, opened ${c.date_opened} at ${c.station}`}>
        <div className="head-actions"><Tags category={c.category} severity={c.severity} /><Status value={c.status} /><a className="btn btn--small" href={`/api/export/cases/${c.case_id}.pdf`}>Download PDF</a></div>
      </PageHead>
      {flags.length > 0 && <div className="flash flash--error">Needs attention: <Flags items={flags} /></div>}
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
            <h2>Files from the citizen</h2>
            <Attachments items={attachments} />
          </section>

          <section className="panel">
            <h2>Evidence</h2>
            {evidence.length === 0 && <p className="muted">No evidence recorded.</p>}
            {evidence.map((e) => (
              <div className="evidence" key={e.evidence_no}>
                <div className="evidence-head"><b>{e.evidence_no}. {e.type}</b><span className="num muted">{e.date_collected}</span></div>
                <p className="prose">{e.description}</p>
                <ol className="custody" aria-label="Chain of custody">
                  {e.custody.map((c2, i) => (
                    <li key={i}>
                      <span className="num muted">{c2.at.slice(0, 16)}</span>
                      <span>{c2.action}{c2.where && `, ${c2.where}`}<span className="muted"> by {c2.by}</span>{c2.note && <span className="muted">. {c2.note}</span>}</span>
                    </li>
                  ))}
                </ol>
                {e.files.length > 0 && <Attachments items={e.files} />}
                {editable && (
                  <details style={{ marginTop: 'var(--space-sm)' }}>
                    <summary>Log movement or attach a file</summary>
                    <form onSubmit={submit(`/evidence/${e.evidence_no}/custody`, 'Movement logged.')}>
                      <div className="row">
                        <Field label="What happened" id={`act-${e.evidence_no}`}><select id={`act-${e.evidence_no}`} name="action">{custody_actions.map((x) => <option key={x}>{x}</option>)}</select></Field>
                        <Field label="Where it is now" id={`where-${e.evidence_no}`}><input id={`where-${e.evidence_no}`} name="where" required /></Field>
                        <Field label="Note" id={`note-${e.evidence_no}`}><input id={`note-${e.evidence_no}`} name="note" /></Field>
                        <button className="btn" type="submit">Log</button>
                      </div>
                    </form>
                    <form onSubmit={sendFile(e.evidence_no)} style={{ marginTop: 'var(--space-sm)' }}>
                      <div className="row">
                        <Field label="File" id={`file-${e.evidence_no}`}><input id={`file-${e.evidence_no}`} name="file" type="file" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt" required /></Field>
                        <button className="btn" type="submit">Attach</button>
                      </div>
                    </form>
                  </details>
                )}
              </div>
            ))}
            {editable && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>Record evidence</summary>
                <form onSubmit={recordEvidence}>
                  <Field label="Type" id="type"><input id="type" name="type" placeholder="Photograph, CCTV, weapon" required /></Field>
                  <Field label="Description" id="ev-desc"><textarea id="ev-desc" name="description" required /><Dictate target="ev-desc" /></Field>
                  <Field label="File (optional)" id="ev-file"><input id="ev-file" name="file" type="file" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt" /></Field>
                  <button className="btn" type="submit">Save evidence</button>
                </form>
              </details>
            )}
          </section>

          <section className="panel">
            <h2>Statements</h2>
            {statements.length === 0 && <p className="muted">No statements recorded.</p>}
            {statements.map((x) => (
              <div className="note" key={x.no}><small>{x.kind}: {x.person}, {x.recorded_at.slice(0, 10)}, recorded by {x.recorded_by}</small><div className="prose">{x.body}</div></div>
            ))}
            {editable && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>Record a statement</summary>
                <form onSubmit={submit('/statements', 'Statement recorded.')}>
                  <div className="row">
                    <Field label="Given by" id="st-kind"><select id="st-kind" name="kind"><option>witness</option><option>victim</option><option>accused</option><option>suspect</option></select></Field>
                    <Field label="Name" id="st-person"><input id="st-person" name="person" required /></Field>
                  </div>
                  <Field label="Statement" id="st-body"><textarea id="st-body" name="body" required /><Dictate target="st-body" /></Field>
                  <button className="btn" type="submit">Save statement</button>
                </form>
              </details>
            )}
          </section>

          <section className="panel">
            <h2>Arrests</h2>
            {arrests.length ? (
              <div className="table-wrap"><table className="data">
                <thead><tr><th>Person</th><th>Date</th><th>Place</th><th>Charges</th></tr></thead>
                <tbody>{arrests.map((x) => <tr key={x.no}><td>{x.person}</td><td className="num">{x.arrested_on}</td><td>{x.place}</td><td>{x.charges}</td></tr>)}</tbody>
              </table></div>
            ) : <p className="muted">Nobody has been arrested in this case.</p>}
            {editable && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>Record an arrest</summary>
                {chargeable.length ? (
                  <form onSubmit={submit('/arrests', 'Arrest recorded.', (b) => ({ ...b, criminal_id: Number(b.criminal_id) }))}>
                    <div className="row">
                      <Field label="Person" id="ar-person"><select id="ar-person" name="criminal_id">{chargeable.map((p) => <option key={p.criminal_id} value={p.criminal_id}>{p.name}</option>)}</select></Field>
                      <Field label="Date" id="ar-date"><input id="ar-date" name="arrested_on" type="date" required /></Field>
                    </div>
                    <div className="row">
                      <Field label="Place" id="ar-place"><input id="ar-place" name="place" required /></Field>
                      <Field label="Charges" id="ar-charges"><input id="ar-charges" name="charges" required /></Field>
                    </div>
                    <button className="btn" type="submit">Save arrest</button>
                  </form>
                ) : <p className="muted">Link a suspect or accused person to the case first.</p>}
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
                  <Field label="Report" id="content"><textarea id="content" name="content" required /><Dictate target="content" /></Field>
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
            {editable && manualStates.length > 0 && (
              <form onSubmit={submit('/status', 'Case status updated.')} style={{ marginTop: 'var(--space-md)' }}>
                <Field label="Move to" id="status"><select id="status" name="status">{manualStates.map((s) => <option key={s}>{s}</option>)}</select></Field>
                <button className="btn btn--primary" type="submit">Update status</button>
              </form>
            )}
          </section>

          <section className="panel">
            <h2>Chargesheet</h2>
            {chargesheet ? (
              <dl className="facts">
                <dt>Filed</dt><dd className="num">{chargesheet.filed_on}</dd>
                <dt>Sections</dt><dd>{chargesheet.sections}</dd>
                <dt>Summary</dt><dd className="prose">{chargesheet.summary}</dd>
              </dl>
            ) : <p className="muted">Not filed yet.</p>}
            {editable && !chargesheet && c.status === 'Under Investigation' && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>File the chargesheet</summary>
                <form onSubmit={submit('/chargesheet', 'Chargesheet filed. The case is now at Chargesheet Filed.')}>
                  <Field label="Sections" id="cs-sections" hint="Needs at least one suspect or accused linked to the case."><input id="cs-sections" name="sections" placeholder="BNS 303" required /></Field>
                  <Field label="Summary" id="cs-summary"><textarea id="cs-summary" name="summary" required /><Dictate target="cs-summary" /></Field>
                  <button className="btn btn--primary" type="submit">File chargesheet</button>
                </form>
              </details>
            )}
          </section>

          <section className="panel">
            <h2>Court dates</h2>
            {court_dates.length === 0 && <p className="muted">{chargesheet ? 'No court dates set.' : 'Court dates can be set once the chargesheet is filed.'}</p>}
            {court_dates.map((d) => (
              <div className="note" key={d.no}>
                <small>{d.date}, {d.court}</small>
                <div>{d.purpose}</div>
                {d.outcome ? <div className="muted">Outcome: {d.outcome}</div> : editable && (
                  <form className="inline-form" onSubmit={submit(`/court-dates/${d.no}/outcome`, 'Outcome saved.')}>
                    <input name="outcome" placeholder="Outcome" aria-label="Outcome" required />
                    <button className="btn btn--small" type="submit">Save</button>
                  </form>
                )}
              </div>
            ))}
            {editable && chargesheet && (
              <details style={{ marginTop: 'var(--space-md)' }}>
                <summary>Set a court date</summary>
                <form onSubmit={submit('/court-dates', 'Court date set.')}>
                  <Field label="Date" id="cd-date"><input id="cd-date" name="date" type="date" required /></Field>
                  <Field label="Court" id="cd-court"><input id="cd-court" name="court" required /></Field>
                  <Field label="Purpose" id="cd-purpose"><input id="cd-purpose" name="purpose" placeholder="First hearing" required /></Field>
                  <button className="btn" type="submit">Set date</button>
                </form>
              </details>
            )}
          </section>

          {user.role === 'admin' && !c.status.startsWith('Closed') && (
            <section className="panel">
              <h2>Assign officer</h2>
              <form onSubmit={submit('/assign', 'Officer assigned.', (b) => ({ officer_id: Number(b.officer_id) }))}>
                <Field label="Officer" id="officer_id">
                  <select id="officer_id" name="officer_id" defaultValue={officers.find((o) => o.name === c.officer_name)?.officer_id}>
                    {officers.map((o) => <option key={o.officer_id} value={o.officer_id}>{o.name}, {o.officer_rank}</option>)}
                  </select>
                </Field>
                <button className="btn" type="submit">Assign</button>
              </form>
            </section>
          )}

          <section className="panel">
            <h2>Timeline</h2>
            <Timeline events={timeline} />
          </section>
        </div>
      </div>
    </>
  );
}
