import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, upload, withQuery } from '../api.js';
import { useSession } from '../session.jsx';
import { Attachments, Crumbs, Download, Empty, Failed, Field, Filters, formData, Loading, PageHead, Pager, Progress, SortTh, Status, useAct, useLoad } from '../ui.jsx';

export function Complaints() {
  const { user } = useSession();
  const [params] = useSearchParams();
  const query = { q: params.get('q') || '', status: params.get('status') || '', page: params.get('page') || '', sort: params.get('sort') || '', dir: params.get('dir') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/complaints', query));
  const citizen = user.role === 'citizen';

  return (
    <>
      <PageHead
        title={citizen ? 'My complaints' : 'Complaints'}
        text={citizen ? 'Everything you have filed, and where it stands.' : 'Every complaint filed at any station.'}
      >
        <div className="head-actions">
          <Download path="/export/complaints.csv" params={params}>Export CSV</Download>
          {citizen && <Link className="btn btn--primary" to="/complaints/new">File a complaint</Link>}
        </div>
      </PageHead>

      <Filters>
        {(p) => (
          <>
            <Field label="Search" id="q"><input id="q" name="q" defaultValue={p.get('q') || ''} placeholder="Title or location" /></Field>
            <Field label="Status" id="status">
              <select id="status" name="status" defaultValue={p.get('status') || ''}>
                <option value="">All</option>
                {['Filed', 'Verified', 'Rejected'].map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <button className="btn" type="submit">Filter</button>
          </>
        )}
      </Filters>

      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <div className="panel">
          {data.items.length === 0 ? (
            query.q || query.status ? (
              <Empty action={<Link className="btn" to="/complaints">Clear filters</Link>}>No complaints match those filters.</Empty>
            ) : citizen ? (
              <Empty action={<Link className="btn btn--primary" to="/complaints/new">File a complaint</Link>}>
                You have not filed a complaint yet. Describe what happened and where, and the station will review it.
              </Empty>
            ) : <Empty>No complaints have been filed yet.</Empty>
          ) : (
            <>
              <div className="table-wrap"><table className="data">
                <thead><tr>
                  <SortTh id="no" className="r">No.</SortTh><SortTh id="title">Title</SortTh>{!citizen && <SortTh id="by">Filed by</SortTh>}
                  <SortTh id="location">Location</SortTh><SortTh id="filed">Filed on</SortTh><SortTh id="status">Status</SortTh><SortTh id="case">Case</SortTh>
                </tr></thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.complaint_id}>
                      <td className="num r">{c.complaint_id}</td>
                      <td><Link to={`/complaints/${c.complaint_id}`}>{c.title}</Link></td>
                      {!citizen && <td>{c.citizen_name}</td>}
                      <td>{c.location}</td>
                      <td className="num">{c.date_filed}</td>
                      <td><Status value={c.status} /></td>
                      <td>{c.case_id ? <Status value={c.case_status} /> : <span className="muted">None</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <Pager page={data.page} pages={data.pages} total={data.total} />
            </>
          )}
        </div>
      )}
    </>
  );
}

export function NewComplaint() {
  const navigate = useNavigate();
  const act = useAct();
  const { notice } = useSession();

  const submit = (event) => {
    const { file, ...body } = formData(event);
    return act(async () => {
      const { complaint_id } = await api('/complaints', { method: 'POST', body });
      let message = 'Complaint filed. You will be notified when it is reviewed.';
      if (file && file.size) {
        // the complaint exists by now, so a rejected file should not lose it
        try { await upload(`/complaints/${complaint_id}/attachments`, file); }
        catch (err) { message = `Complaint filed, but the file was not added: ${err.message}`; }
      }
      notice(message, 'ok', true);
      navigate(`/complaints/${complaint_id}`);
    });
  };

  return (
    <>
      <PageHead title="File a complaint" text="The station reviews every complaint before a case is opened." />
      <form className="panel form-narrow" onSubmit={submit}>
        <Field label="Short title" id="title"><input id="title" name="title" maxLength={120} required /></Field>
        <Field label="What happened" id="description"><textarea id="description" name="description" required /></Field>
        <div className="row">
          <Field label="Where" id="location"><input id="location" name="location" maxLength={200} required /></Field>
          <Field label="Date of incident" id="incident_date"><input id="incident_date" name="incident_date" type="date" required /></Field>
        </div>
        <Field label="Attach a file" id="file" hint="Optional. An image, PDF or text file, up to 5 MB.">
          <input id="file" name="file" type="file" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt" />
        </Field>
        <div className="row" style={{ marginTop: 'var(--space-md)' }}>
          <button className="btn btn--primary" type="submit">Submit complaint</button>
          <Link className="btn" to="/complaints">Cancel</Link>
        </div>
      </form>
    </>
  );
}

export function Complaint() {
  const { id } = useParams();
  const { user, notice } = useSession();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useLoad(`/complaints/${id}`);
  const act = useAct(reload);
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={error.status === 404 ? undefined : reload} />;

  const { complaint: c, case: kase, notes, history, attachments, stations, can_add_note } = data;
  const staff = user.role !== 'citizen';
  const post = (path, body, ok) => act(() => api(`/complaints/${id}${path}`, { method: 'POST', body }), ok);

  const addNote = async (event) => {
    const body = formData(event);
    const form = event.target;
    await post('/notes', body, 'Added to your complaint.');
    form.reset();
  };
  const addFile = async (event) => {
    const { file } = formData(event);
    const form = event.target;
    if (!file || !file.size) return;
    const done = await act(() => upload(`/complaints/${id}/attachments`, file), 'File added.');
    if (done) form.reset();
  };
  const openCase = (event) => {
    const { station_id } = formData(event);
    return act(async () => {
      const { case_id } = await api(`/complaints/${id}/register-case`, { method: 'POST', body: { station_id: Number(station_id) } });
      notice('Case registered.', 'ok', true);
      navigate(`/cases/${case_id}`);
    });
  };

  return (
    <>
      <Crumbs trail={[['Complaints', '/complaints']]} here={`No. ${c.complaint_id}`} />
      <PageHead title={c.title} text={`Filed by ${c.citizen_name} on ${c.date_filed}`}><Status value={c.status} /></PageHead>
      <Progress complaint={c} kase={kase} />

      <div className="cols">
        <div>
          <section className="panel">
            <h2>Complaint</h2>
            <dl className="facts">
              <dt>Where</dt><dd>{c.location}</dd>
              <dt>Incident date</dt><dd className="num">{c.incident_date}</dd>
              <dt>Description</dt><dd className="prose">{c.description}</dd>
              {c.status === 'Rejected' && <><dt>Reason</dt><dd>{c.reject_reason}</dd></>}
            </dl>
          </section>

          <section className="panel">
            <h2>Files</h2>
            <Attachments items={attachments} />
            {can_add_note && attachments.length < 5 && (
              <form onSubmit={addFile} style={{ marginTop: 'var(--space-md)' }}>
                <Field label="Attach a file" id="file" hint="An image, PDF or text file, up to 5 MB.">
                  <input id="file" name="file" type="file" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt" required />
                </Field>
                <button className="btn" type="submit">Upload</button>
              </form>
            )}
          </section>

          <section className="panel">
            <h2>Statements and evidence</h2>
            {notes.length === 0 && <p className="muted">Nothing added yet.</p>}
            {notes.map((n, i) => (
              <div className="note" key={i}>
                <small>{n.kind === 'statement' ? 'Statement' : 'Evidence'}, {n.created_at}</small>
                <div className="prose">{n.body}</div>
              </div>
            ))}
            {can_add_note && (
              <form onSubmit={addNote} style={{ marginTop: 'var(--space-md)' }}>
                <Field label="Type" id="kind">
                  <select id="kind" name="kind"><option value="statement">Statement</option><option value="evidence">Evidence description</option></select>
                </Field>
                <Field label="Details" id="body"><textarea id="body" name="body" required /></Field>
                <button className="btn" type="submit">Add</button>
              </form>
            )}
          </section>
        </div>

        <div>
          <section className="panel">
            <h2>Case</h2>
            {kase ? (
              <>
                <dl className="facts">
                  <dt>Status</dt><dd><Status value={kase.status} /></dd>
                  <dt>Station</dt><dd>{kase.station}</dd>
                  <dt>Officer</dt><dd>{kase.officer_name || 'Not assigned yet'}</dd>
                  <dt>Opened</dt><dd className="num">{kase.date_opened}</dd>
                </dl>
                {staff && <p style={{ marginTop: 'var(--space-md)' }}><Link className="btn" to={`/cases/${kase.case_id}`}>Open case file</Link></p>}
              </>
            ) : (
              <p className="muted">
                {c.status === 'Filed' ? 'A case opens once the station verifies this complaint.'
                  : c.status === 'Rejected' ? 'No case was opened.'
                  : 'Verified. Waiting for the station to register a case.'}
              </p>
            )}
          </section>

          {staff && c.status !== 'Rejected' && !kase && (
            <section className="panel">
              <h2>Review</h2>
              {c.status === 'Filed' ? (
                <>
                  <button className="btn btn--primary" onClick={() => post('/verify', {}, 'Complaint verified.')}>Verify complaint</button>
                  <details style={{ marginTop: 'var(--space-md)' }}>
                    <summary>Reject with a reason</summary>
                    <form onSubmit={(e) => post('/reject', formData(e), 'Complaint rejected.')}>
                      <Field label="Reason" id="reason"><textarea id="reason" name="reason" required /></Field>
                      <button className="btn btn--danger" type="submit">Reject complaint</button>
                    </form>
                  </details>
                </>
              ) : (
                <form onSubmit={openCase}>
                  <Field label="Station" id="station_id">
                    <select id="station_id" name="station_id" required>{stations.map((s) => <option key={s.station_id} value={s.station_id}>{s.name}</option>)}</select>
                  </Field>
                  <button className="btn btn--primary" type="submit">Register case</button>
                </form>
              )}
            </section>
          )}

          <section className="panel">
            <h2>History</h2>
            <ul className="trail">
              {history.map((h, i) => (
                <li key={i}>
                  <span>{h.new_status}{h.who && <span className="muted"> by {h.who}</span>}</span>
                  <span className="num muted">{h.changed_at.slice(0, 10)}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
