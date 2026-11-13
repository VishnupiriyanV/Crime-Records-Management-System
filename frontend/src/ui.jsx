import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import { useSession } from './session.jsx';
import { useT } from './i18n.jsx';

// loads a GET endpoint and exposes reload; error and loading are states the page must draw
export function useLoad(path) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = useCallback(() => {
    setState((s) => ({ ...s, error: null, loading: s.data === null }));
    return api(path)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: null, error, loading: false }));
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load };
}

// runs a write, tells the user what happened, then lets the page refresh
export function useAct(after) {
  const { notice, refresh } = useSession();
  return useCallback(async (call, success) => {
    try {
      const result = await call();
      if (success) notice(success, 'ok');
      await after?.(result);
      refresh();
      return result;
    } catch (err) {
      notice(err.message, 'error');
    }
  }, [after, notice, refresh]);
}

export function formData(event) {
  event.preventDefault();
  return Object.fromEntries(new FormData(event.target));
}

export function useTitle(title) {
  const t = useT();
  useEffect(() => { document.title = `${t(title)} | CRMS`; }, [title, t]);
}

export function PageHead({ title, text, data, children }) {
  const t = useT();
  useTitle(title);
  return <div className="page-head"><div><h1 className={data ? 'raw' : undefined}>{data ? title : t(title)}</h1>{text && <p>{t(text)}</p>}</div>{children}</div>;
}

export function Crumbs({ trail, here }) {
  const t = useT();
  return (
    <div className="crumbs">
      {trail.map(([label, to]) => <span key={to}><Link to={to}>{t(label)}</Link> / </span>)}{here}
    </div>
  );
}

export function Status({ value, reason }) {
  const t = useT();
  // a complaint the citizen took back is stored as rejected with this reason, and shown as withdrawn
  if (value === 'Rejected' && reason === 'Withdrawn by the citizen.') return <span className="badge">{t('Withdrawn')}</span>;
  const kind = value === 'Rejected' ? 'bad'
    : ['Closed (Resolved)', 'Verified'].includes(value) ? 'good'
    : ['Under Investigation', 'Chargesheet Filed', 'Filed'].includes(value) ? 'open' : '';
  return <span className={`badge ${kind ? `badge--${kind}` : ''}`}>{t(value)}</span>;
}

export function Loading() {
  return <div className="panel" aria-busy="true"><div className="skeleton" /><div className="skeleton" /><div className="skeleton short" /></div>;
}

export function Failed({ error, retry }) {
  const t = useT();
  return (
    <div className="panel">
      <div className="empty">
        <p>{t(error.message)}</p>
        {retry && <button className="btn" onClick={retry}>{t('Try again')}</button>}
      </div>
    </div>
  );
}

export function Empty({ children, action }) {
  const t = useT();
  return <div className="empty"><p>{typeof children === 'string' ? t(children) : children}</p>{action}</div>;
}

export function Pager({ page, pages, total }) {
  const t = useT();
  const [params, setParams] = useSearchParams();
  const go = (p) => { const next = new URLSearchParams(params); next.set('page', p); setParams(next); };
  return (
    <div className="pager">
      <span>{t(total === 1 ? '{n} result, page {page} of {pages}' : '{n} results, page {page} of {pages}', { n: total, page, pages })}</span>
      <div>
        {page > 1 && <button className="btn btn--small" onClick={() => go(page - 1)}>{t('Previous')}</button>}
        {page < pages && <button className="btn btn--small" onClick={() => go(page + 1)}>{t('Next')}</button>}
      </div>
    </div>
  );
}

// the filter row keeps its state in the URL so a list can be shared or reloaded
export function Filters({ children }) {
  const [params, setParams] = useSearchParams();
  const submit = (e) => {
    e.preventDefault();
    const next = new URLSearchParams();
    for (const [k, v] of new FormData(e.target)) if (v) next.set(k, v);
    setParams(next);
  };
  return <form className="filters" onSubmit={submit} key={params.toString()}><div className="row">{children(params)}</div></form>;
}

export function Field({ label, id, children, hint }) {
  const t = useT();
  return (
    <div className="field">
      <label htmlFor={id}>{t(label)}</label>
      {children}
      {hint && <small>{t(hint)}</small>}
    </div>
  );
}

const sizeLabel = (n) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

const kindOf = (type) => (type.startsWith('image/') ? 'image' : type === 'application/pdf' ? 'pdf' : type === 'text/plain' ? 'text' : '');

function PreviewBody({ file, url }) {
  const kind = kindOf(file.content_type);
  const [text, setText] = useState('');
  useEffect(() => {
    if (kind === 'text') fetch(url, { credentials: 'same-origin' }).then((r) => r.text()).then(setText).catch(() => setText('Could not load this file.'));
  }, [kind, url]);
  if (kind === 'image') return <img src={url} alt={file.filename} className="preview-image" />;
  if (kind === 'pdf') return <iframe src={url} title={file.filename} className="preview-frame" />;
  return <pre className="preview-text">{text}</pre>;
}

export function Attachments({ items }) {
  const dialog = useRef(null);
  const [shown, setShown] = useState(null);
  const t = useT();
  if (!items.length) return <p className="muted">{t('No files attached.')}</p>;

  const open = (file) => { setShown(file); dialog.current?.showModal(); };
  const close = () => { dialog.current?.close(); setShown(null); };
  const url = (a) => `/api/attachments/${a.attachment_id}`;

  return (
    <>
      <ul className="trail">
        {items.map((a) => (
          <li key={a.attachment_id}>
            <span>
              {kindOf(a.content_type) ? <button className="link-btn" onClick={() => open(a)}>{a.filename}</button> : a.filename}
              {' '}<a className="muted" href={url(a)}>{t('Download')}</a>
              {a.sha256 && <small className="fingerprint" title={a.sha256}>{t('SHA-256')} {a.sha256.slice(0, 16)}&hellip;</small>}
            </span>
            <span className="num muted">{sizeLabel(a.size)}</span>
          </li>
        ))}
      </ul>
      <dialog ref={dialog} className="preview" onClose={() => setShown(null)} onClick={(e) => e.target === dialog.current && close()}>
        {shown && (
          <>
            <div className="preview-head"><b>{shown.filename}</b><button className="link-btn" onClick={close}>{t('Close')}</button></div>
            <PreviewBody file={shown} url={`${url(shown)}?inline=1`} />
          </>
        )}
      </dialog>
    </>
  );
}

// names a way of filtering a list, so it can be opened again in one click; each person keeps their own
export function SavedViews({ page }) {
  const t = useT();
  const [params] = useSearchParams();
  const { notice } = useSession();
  const { data, reload } = useLoad(`/views?page=${page}`);
  const current = new URLSearchParams(params);
  current.delete('page');
  const query = current.toString();
  const views = data?.items || [];

  const save = async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api('/views', { method: 'POST', body: { page, name: new FormData(form).get('name'), query } });
      form.reset();
      notice('View saved.', 'ok');
      reload();
    } catch (err) { notice(err.message, 'error'); }
  };
  const remove = async (view) => {
    try { await api(`/views/${view.view_id}`, { method: 'DELETE' }); reload(); } catch (err) { notice(err.message, 'error'); }
  };

  if (!views.length && !query) return null;
  return (
    <div className="views">
      {views.length > 0 && (
        <ul className="views-list" aria-label={t('Saved views')}>
          {views.map((v) => (
            <li key={v.view_id}>
              <Link to={`/${page}${v.query ? `?${v.query}` : ''}`} aria-current={v.query === query ? 'true' : undefined}>{v.name}</Link>
              <button type="button" className="link-btn muted" aria-label={t('Delete the view {name}', { name: v.name })} onClick={() => remove(v)}>&times;</button>
            </li>
          ))}
        </ul>
      )}
      {query && (
        <form className="views-save" onSubmit={save}>
          <input name="name" maxLength={60} placeholder={t('Name this filter')} aria-label={t('Name this filter')} required />
          <button className="btn btn--small" type="submit">{t('Save view')}</button>
        </form>
      )}
    </div>
  );
}

// a column heading that sorts the list through the URL; the server does the sorting
export function SortTh({ id, children, className }) {
  const [params, setParams] = useSearchParams();
  const active = params.get('sort') === id;
  const dir = params.get('dir') === 'asc' ? 'asc' : 'desc';
  const click = () => {
    const next = new URLSearchParams(params);
    next.set('sort', id);
    next.set('dir', active && dir === 'asc' ? 'desc' : 'asc');
    next.delete('page');
    setParams(next);
  };
  const t = useT();
  return (
    <th className={className} aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}>
      <button className="sort-btn" onClick={click}>{typeof children === 'string' ? t(children) : children}<span aria-hidden="true">{active ? (dir === 'asc' ? ' \u2191' : ' \u2193') : ''}</span></button>
    </th>
  );
}

// a link to a server-built file (CSV or PDF) that keeps the list's current filters
export function Download({ path, params, children }) {
  const t = useT();
  const query = {};
  for (const key of ['q', 'status', 'mine', 'wanted', 'sort', 'dir']) if (params?.get(key)) query[key] = params.get(key);
  const href = `/api${path}${Object.keys(query).length ? `?${new URLSearchParams(query)}` : ''}`;
  return <a className="btn btn--small" href={href}>{typeof children === 'string' ? t(children) : children}</a>;
}

// the crime type and how serious it was judged to be
// small red notes for work that has waited too long
export function Flags({ items }) {
  const t = useT();
  if (!items || !items.length) return null;
  return <span className="flags">{items.map((f) => <span key={f.kind} className="badge badge--bad">{t(f.text)}</span>)}</span>;
}

export function Tags({ category, severity }) {
  const t = useT();
  return (
    <span className="tags">
      <span className="badge">{t(category)}</span>
      <span className={`badge ${severity === 'High' ? 'badge--bad' : ''}`}>{t(severity)}</span>
    </span>
  );
}

// a person's photo, or their initials when there is none
export function Avatar({ officerId, name, has, size = 56 }) {
  const initials = name.split(' ').map((w) => w[0]).slice(0, 2).join('');
  return has
    ? <img className="avatar" style={{ width: size, height: size }} src={`/api/officers/${officerId}/photo`} alt="" />
    : <span className="avatar avatar--blank" style={{ width: size, height: size }} aria-hidden="true">{initials}</span>;
}

const STAGES = ['Filed', 'Verified', 'Case opened', 'Resolved'];

// where a complaint is on its way from filing to a closed case
export function Progress({ complaint, kase }) {
  const t = useT();
  let reached = 0;
  if (complaint.status === 'Verified') reached = 1;
  if (kase) reached = kase.status === 'Closed (Resolved)' || kase.status === 'Closed (Unresolved)' ? 3 : 2;
  const rejected = complaint.status === 'Rejected';
  const stages = rejected ? ['Filed', 'Rejected'] : kase?.status === 'Closed (Unresolved)' ? ['Filed', 'Verified', 'Case opened', 'Closed, unresolved'] : STAGES;
  const last = rejected ? 1 : reached;
  return (
    <ol className="progress" aria-label={t('Complaint progress')}>
      {stages.map((label, i) => (
        <li key={label} className={i < last ? 'done' : i === last ? 'now' : ''} aria-current={i === last ? 'step' : undefined}>
          <span className={`dot ${rejected && i === 1 ? 'dot--bad' : ''}`} />{t(label)}
        </li>
      ))}
    </ol>
  );
}

// the merged story of a case, oldest first
export function Timeline({ events }) {
  const t = useT();
  return (
    <ol className="timeline">
      {events.map((e, i) => (
        <li key={i} className={`timeline-${e.kind}`}>
          <span className="num muted">{e.at.slice(0, 19)}</span>
          <span>
            {e.text}{e.who && <span className="muted"> {t('by {who}', { who: e.who })}</span>}
            {e.detail && <span className="timeline-detail muted">{e.detail}</span>}
            <span className={`seal${e.seal ? '' : ' seal--none'}`} title={e.seal ? t('Sealed {when} by {who}', { when: e.seal.sealed_at.slice(0, 19), who: e.seal.sealed_by }) : t('Not covered by the seal')}>
              {e.seal ? `#${e.seal.seq} ${e.seal.hash}${e.seal.imported ? ` ${t('imported')}` : ''}` : t('not sealed')}
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}
