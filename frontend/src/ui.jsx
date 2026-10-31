import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import { useSession } from './session.jsx';

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
  useEffect(() => { document.title = `${title} | CRMS`; }, [title]);
}

export function PageHead({ title, text, children }) {
  useTitle(title);
  return <div className="page-head"><div><h1>{title}</h1>{text && <p>{text}</p>}</div>{children}</div>;
}

export function Crumbs({ trail, here }) {
  return (
    <div className="crumbs">
      {trail.map(([label, to]) => <span key={to}><Link to={to}>{label}</Link> / </span>)}{here}
    </div>
  );
}

export function Status({ value }) {
  const kind = value === 'Rejected' ? 'bad'
    : ['Closed (Resolved)', 'Verified'].includes(value) ? 'good'
    : ['Under Investigation', 'Chargesheet Filed', 'Filed'].includes(value) ? 'open' : '';
  return <span className={`badge ${kind ? `badge--${kind}` : ''}`}>{value}</span>;
}

export function Loading() {
  return <div className="panel" aria-busy="true"><div className="skeleton" /><div className="skeleton" /><div className="skeleton short" /></div>;
}

export function Failed({ error, retry }) {
  return (
    <div className="panel">
      <div className="empty">
        <p>{error.message}</p>
        {retry && <button className="btn" onClick={retry}>Try again</button>}
      </div>
    </div>
  );
}

export function Empty({ children, action }) {
  return <div className="empty"><p>{children}</p>{action}</div>;
}

export function Pager({ page, pages, total }) {
  const [params, setParams] = useSearchParams();
  const go = (p) => { const next = new URLSearchParams(params); next.set('page', p); setParams(next); };
  return (
    <div className="pager">
      <span>{total} result{total === 1 ? '' : 's'}, page {page} of {pages}</span>
      <div>
        {page > 1 && <button className="btn btn--small" onClick={() => go(page - 1)}>Previous</button>}
        {page < pages && <button className="btn btn--small" onClick={() => go(page + 1)}>Next</button>}
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
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && <small>{hint}</small>}
    </div>
  );
}

const sizeLabel = (n) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

export function Attachments({ items }) {
  if (!items.length) return <p className="muted">No files attached.</p>;
  return (
    <ul className="trail">
      {items.map((a) => (
        <li key={a.attachment_id}>
          <a href={`/api/attachments/${a.attachment_id}`}>{a.filename}</a>
          <span className="num muted">{sizeLabel(a.size)}</span>
        </li>
      ))}
    </ul>
  );
}
