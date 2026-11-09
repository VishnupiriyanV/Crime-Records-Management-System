import { useCallback, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, upload, withQuery } from '../api.js';
import { MiniMap, PinPicker } from '../MapView.jsx';
import { useSession } from '../session.jsx';
import { Attachments, Crumbs, Download, Empty, Failed, Field, Filters, formData, Loading, PageHead, Pager, Flags, Progress, SortTh, Plane, Status, Tags, useAct, useLoad } from '../ui.jsx';
import { Dictate, SpeakComplaint } from '../voice.jsx';
import { useT } from '../i18n.jsx';

export function Complaints() {
  const t = useT();
  const { user } = useSession();
  const [params] = useSearchParams();
  const query = { q: params.get('q') || '', status: params.get('status') || '', category: params.get('category') || '', severity: params.get('severity') || '', page: params.get('page') || '', sort: params.get('sort') || '', dir: params.get('dir') || '' };
  const { data, error, loading, reload } = useLoad(withQuery('/complaints', query));
  const citizen = user.role === 'citizen';

  return (
    <>
      <PageHead
        title={citizen ? 'My complaints' : 'Complaints'}
        text={citizen ? 'Everything you have filed, and where it stands.' : 'Every complaint filed at any station.'}
      >
        <div className="head-actions">
          <Download path="/export/complaints.csv" params={params}>{t('Export CSV')}</Download>
          {citizen && <Link className="btn btn--primary" to="/complaints/new">{t('File a complaint')}</Link>}
        </div>
      </PageHead>

      <Filters>
        {(p) => (
          <>
            <Field label="Search" id="q"><input id="q" name="q" defaultValue={p.get('q') || ''} placeholder={t('Title, location or FIR number')} /></Field>
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
            <Field label="Status" id="status">
              <select id="status" name="status" defaultValue={p.get('status') || ''}>
                <option value="">{t('All')}</option>
                {['Filed', 'Verified', 'Rejected'].map((x) => <option key={x} value={x}>{t(x)}</option>)}
              </select>
            </Field>
            <button className="btn" type="submit">{t('Filter')}</button>
          </>
        )}
      </Filters>

      {loading ? <Loading /> : error ? <Failed error={error} retry={reload} /> : (
        <div className="panel">
          {data.items.length === 0 ? (
            query.q || query.status || query.category || query.severity ? (
              <Empty action={<Link className="btn" to="/complaints">{t('Clear filters')}</Link>}>{t('No complaints match those filters.')}</Empty>
            ) : citizen ? (
              <Empty action={<Link className="btn btn--primary" to="/complaints/new">{t('File a complaint')}</Link>}>{t('You have not filed a complaint yet. Describe what happened and where, and the station will review it.')}</Empty>
            ) : <Empty>{t('No complaints have been filed yet.')}</Empty>
          ) : (
            <>
              <div className="table-wrap"><table className="data">
                <thead><tr>
                  <SortTh id="no">{t('FIR no.')}</SortTh><SortTh id="title">{t('Title')}</SortTh><SortTh id="category">{t('Category')}</SortTh>{!citizen && <SortTh id="by">{t('Filed by')}</SortTh>}
                  <SortTh id="location">{t('Location')}</SortTh><SortTh id="filed">{t('Filed on')}</SortTh><SortTh id="status">{t('Status')}</SortTh><SortTh id="case">{t('Case')}</SortTh>
                </tr></thead>
                <tbody>
                  {data.items.map((c) => (
                    <tr key={c.complaint_id}>
                      <td className="num">{c.fir_no}</td>
                      <td><Link to={`/complaints/${c.complaint_id}`}>{c.title}</Link><Flags items={c.flags} /></td>
                      <td><Tags category={c.category} severity={c.severity} /></td>
                      {!citizen && <td>{c.citizen_name}</td>}
                      <td>{c.location}</td>
                      <td className="num">{c.date_filed}</td>
                      <td><Status value={c.status} /></td>
                      <td>{c.case_id ? <Status value={c.case_status} /> : <span className="muted">{t('None')}</span>}</td>
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
  const t = useT();
  const navigate = useNavigate();
  const act = useAct();
  const { notice } = useSession();
  const { data } = useLoad('/meta');
  const [pin, setPin] = useState(null);
  const pick = useCallback((at) => setPin(at), []);
  const [sending, setSending] = useState(false);
  const [similar, setSimilar] = useState([]);
  const skipCheck = useRef(false);
  const formRef = useRef(null);

  const useMyLocation = () => {
    if (!navigator.geolocation) return notice('This browser cannot share a location.', 'error');
    navigator.geolocation.getCurrentPosition(
      (pos) => setPin({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => notice('Could not get your location. Click the map instead.', 'error'),
    );
  };

  const submit = (event) => {
    const { file, ...body } = formData(event);
    if (pin) { body.latitude = pin.lat; body.longitude = pin.lng; }
    if (sending) return;
    setSending(true);
    return act(async () => {
      if (!skipCheck.current) {
        // warn about a complaint of the person's own that looks the same; if the check fails, filing goes ahead
        let found = [];
        try { found = (await api('/complaints/check', { method: 'POST', body })).items; } catch { /* not worth blocking the complaint */ }
        if (found.length) { setSimilar(found); setSending(false); return; }
      }
      skipCheck.current = false;
      let complaint_id;
      try {
        ({ complaint_id } = await api('/complaints', { method: 'POST', body }));
      } catch (err) {
        setSending(false);
        throw err;
      }
      let message = 'Complaint filed. You will be notified when it is reviewed.';
      if (file && file.size) {
        // the complaint exists by now, so a rejected file should not lose it
        try { await upload(`/complaints/${complaint_id}/attachments`, file); }
        catch (err) { message = t('Complaint filed, but the file was not added: {error}', { error: err.message }); }
      }
      notice(message, 'ok', true);
      navigate(`/complaints/${complaint_id}`);
    });
  };

  return (
    <>
      <PageHead title={t('File a complaint')} text="The station reviews every complaint before a case is opened." />
      <form className="panel form-narrow" onSubmit={submit} ref={formRef}>
        <SpeakComplaint />
        <Field label="Short title" id="title"><input id="title" name="title" maxLength={120} required /></Field>
        <Field label="What happened" id="description">
          <textarea id="description" name="description" required />
          <Dictate target="description" />
        </Field>
        <div className="row">
          <Field label="Category" id="category">
            <select id="category" name="category" defaultValue="Other">{(data?.categories || ['Other']).map((c) => <option key={c} value={c}>{t(c)}</option>)}</select>
          </Field>
          <Field label="Date of incident" id="incident_date"><input id="incident_date" name="incident_date" type="date" required /></Field>
        </div>
        <Field label="Where" id="location"><input id="location" name="location" maxLength={200} required /></Field>
        <div className="field">
          <label>{t('Pin it on the map')} <span className="muted">{t('(optional)')}</span></label>
          <PinPicker value={pin} onChange={pick} />
          <div className="row map-actions">
            <button type="button" className="btn btn--small" onClick={useMyLocation}>{t('Use my location')}</button>
            {pin && <button type="button" className="btn btn--small" onClick={() => setPin(null)}>{t('Remove pin')}</button>}
          </div>
        </div>
        <Field label="Attach a file" id="file" hint="Optional. An image, PDF or text file, up to 5 MB.">
          <input id="file" name="file" type="file" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt" />
        </Field>
        {similar.length > 0 && (
          <div className="voice-panel" role="alert">
            <b>{t('You may have filed this already')}</b>
            <ul className="trail">
              {similar.map((x) => (
                <li key={x.complaint_id}>
                  <span><Link to={`/complaints/${x.complaint_id}`}>{x.fir_no} {x.title}</Link> <span className="muted">{t(x.status)}, {x.reasons.map((r) => t(r)).join(', ')}</span></span>
                </li>
              ))}
            </ul>
            <div className="voice-row">
              <button type="button" className="btn btn--small" onClick={() => { skipCheck.current = true; setSimilar([]); formRef.current.requestSubmit(); }}>
                {t('This is a different incident, file it')}
              </button>
            </div>
          </div>
        )}
        <div className="row" style={{ marginTop: 'var(--space-md)' }}>
          <button className="btn btn--primary" type="submit" disabled={sending}>{t(sending ? 'Submitting...' : 'Submit complaint')}</button>
          <Link className="btn" to="/complaints">{t('Cancel')}</Link>
        </div>
      </form>
    </>
  );
}

export function Complaint() {
  const t = useT();
  const { id } = useParams();
  const { user, notice } = useSession();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useLoad(`/complaints/${id}`);
  const act = useAct(reload);
  if (loading) return <Loading />;
  if (error) return <Failed error={error} retry={error.status === 404 ? undefined : reload} />;

  const { complaint: c, case: kase, notes, history, attachments, stations, can_add_note, categories, severities, flags } = data;
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
  const classify = (event) => post('/classify', formData(event), 'Classification saved.');
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
      <Crumbs trail={[['Complaints', '/complaints']]} here={t('No. {id}', { id: c.complaint_id })} />
      <PageHead title={c.title} text={t('{fir}, filed by {name} on {date}', { fir: c.fir_no, name: c.citizen_name, date: c.date_filed })}><div className="head-actions"><Tags category={c.category} severity={c.severity} />{kase ? <Plane value={kase.status} date={kase.date_opened} /> : <Plane value={c.status} date={[...history].reverse().find((h) => h.new_status === c.status)?.changed_at || c.date_filed} />}</div></PageHead>
      {flags && flags.length > 0 && <div className="flash flash--error">{t('Needs attention:')}{' '}<Flags items={flags} /></div>}
      <Progress complaint={c} kase={kase} />

      <div className="cols">
        <div>
          <section className="panel">
            <h2>{t('Complaint')}</h2>
            <dl className="facts">
              <dt>{t('Where')}</dt><dd>{c.location}</dd>
              <dt>{t('Incident date')}</dt><dd className="num">{c.incident_date}</dd>
              <dt>{t('Description')}</dt><dd className="prose">{c.description}</dd>
              {c.status === 'Rejected' && <><dt>{t('Reason')}</dt><dd>{c.reject_reason}</dd></>}
            </dl>
            {c.latitude != null && <div style={{ marginTop: 'var(--space-md)' }}><MiniMap lat={c.latitude} lng={c.longitude} /></div>}
          </section>

          <section className="panel">
            <h2>{t('Files')}</h2>
            <Attachments items={attachments} />
            {can_add_note && attachments.length < 5 && (
              <form onSubmit={addFile} style={{ marginTop: 'var(--space-md)' }}>
                <Field label="Attach a file" id="file" hint="An image, PDF or text file, up to 5 MB.">
                  <input id="file" name="file" type="file" accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.txt" required />
                </Field>
                <button className="btn" type="submit">{t('Upload')}</button>
              </form>
            )}
          </section>

          <section className="panel">
            <h2>{t('Statements and evidence')}</h2>
            {notes.length === 0 && <p className="muted">{t('Nothing added yet.')}</p>}
            {notes.map((n, i) => (
              <div className="note" key={i}>
                <small>{t(n.kind === 'statement' ? 'Statement' : 'Evidence')}, {n.created_at}</small>
                <div className="prose">{n.body}</div>
              </div>
            ))}
            {can_add_note && (
              <form onSubmit={addNote} style={{ marginTop: 'var(--space-md)' }}>
                <Field label="Type" id="kind">
                  <select id="kind" name="kind"><option value="statement">{t('Statement')}</option><option value="evidence">{t('Evidence description')}</option></select>
                </Field>
                <Field label="Details" id="body"><textarea id="body" name="body" required /></Field>
                <button className="btn" type="submit">{t('Add')}</button>
              </form>
            )}
          </section>
        </div>

        <div>
          <section className="panel">
            <h2>{t('Case')}</h2>
            {kase ? (
              <>
                <dl className="facts">
                  <dt>{t('Status')}</dt><dd><Status value={kase.status} /></dd>
                  <dt>{t('Station')}</dt><dd>{kase.station}</dd>
                  <dt>{t('Officer')}</dt><dd>{kase.officer_name || t('Not assigned yet')}</dd>
                  <dt>{t('Opened')}</dt><dd className="num">{kase.date_opened}</dd>
                </dl>
                {staff && <p style={{ marginTop: 'var(--space-md)' }}><Link className="btn" to={`/cases/${kase.case_id}`}>{t('Open case file')}</Link></p>}
              </>
            ) : (
              <p className="muted">
                {t(c.status === 'Filed' ? 'A case opens once the station verifies this complaint.'
                  : c.status === 'Rejected' ? 'No case was opened.'
                  : 'Verified. Waiting for the station to register a case.')}
              </p>
            )}
          </section>

          {staff && (
            <section className="panel">
              <h2>{t('Classification')}</h2>
              <form onSubmit={classify}>
                <Field label="Category" id="cl-category"><select id="cl-category" name="category" defaultValue={c.category}>{categories.map((x) => <option key={x} value={x}>{t(x)}</option>)}</select></Field>
                <Field label="Severity" id="cl-severity"><select id="cl-severity" name="severity" defaultValue={c.severity}>{severities.map((x) => <option key={x} value={x}>{t(x)}</option>)}</select></Field>
                <button className="btn" type="submit">{t('Save')}</button>
              </form>
            </section>
          )}

          {staff && <Similar id={id} canReject={c.status === 'Filed'} reject={(reason) => post('/reject', { reason }, 'Rejected as a duplicate.')} />}

          {staff && c.status !== 'Rejected' && !kase && (
            <section className="panel">
              <h2>{t('Review')}</h2>
              {c.status === 'Filed' ? (
                <>
                  <button className="btn btn--primary" onClick={() => post('/verify', {}, 'Complaint verified.')}>{t('Verify complaint')}</button>
                  <details style={{ marginTop: 'var(--space-md)' }}>
                    <summary>{t('Reject with a reason')}</summary>
                    <form onSubmit={(e) => post('/reject', formData(e), 'Complaint rejected.')}>
                      <Field label="Reason" id="reason"><textarea id="reason" name="reason" required /></Field>
                      <button className="btn btn--danger" type="submit">{t('Reject complaint')}</button>
                    </form>
                  </details>
                </>
              ) : (
                <form onSubmit={openCase}>
                  <Field label="Station" id="station_id">
                    <select id="station_id" name="station_id" required>{stations.map((s) => <option key={s.station_id} value={s.station_id}>{s.name}</option>)}</select>
                  </Field>
                  <button className="btn btn--primary" type="submit">{t('Register case')}</button>
                </form>
              )}
            </section>
          )}

          <section className="panel">
            <h2>{t('History')}</h2>
            <ul className="trail">
              {history.map((h, i) => (
                <li key={i}>
                  <span><Plane compact value={h.new_status} />{h.who && <span className="muted"> {t('by {who}', { who: h.who })}</span>}</span>
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

// other complaints that look like this one, so a duplicate can be spotted before it is worked twice
function Similar({ id, canReject, reject }) {
  const t = useT();
  const { data } = useLoad(`/complaints/${id}/similar`);
  if (!data || data.items.length === 0) return null;
  return (
    <section className="panel">
      <h2>{t('Possible duplicates')}</h2>
      <ul className="trail">
        {data.items.map((s) => (
          <li key={s.complaint_id}>
            <span>
              <Link to={`/complaints/${s.complaint_id}`}>{s.fir_no}</Link> {s.title}
              <div className="muted">{s.reasons.map((r) => t(r)).join(', ')}. {t(s.status)}.</div>
            </span>
            {canReject && <button className="link-btn" onClick={() => reject(`Duplicate of ${s.fir_no}`)}>{t('Reject as duplicate')}</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}
