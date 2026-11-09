import { useState } from 'react';
import { api } from '../api.js';
import { Empty, Failed, Field, Loading, PageHead, useAct, useLoad } from '../ui.jsx';

// a secret that is shown once; after this the server only keeps a hash (tokens) or hands nothing back (webhooks)
function ShownOnce({ title, value, onClose }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); } catch { /* the text is selectable instead */ }
  };
  return (
    <div className="voice-panel" role="status">
      <b>{title}</b>
      <code style={{ overflowWrap: 'anywhere', userSelect: 'all' }}>{value}</code>
      <div className="voice-row">
        <button type="button" className="btn btn--small" onClick={copy}>{copied ? 'Copied' : 'Copy'}</button>
        <button type="button" className="btn btn--small" onClick={onClose}>I have saved it</button>
      </div>
    </div>
  );
}

export function Integrations() {
  const tokens = useLoad('/tokens');
  const hooks = useLoad('/webhooks');
  const reload = () => { tokens.reload(); hooks.reload(); };
  const act = useAct(reload);
  const [shown, setShown] = useState(null);
  if (tokens.loading || hooks.loading) return <Loading />;
  if (tokens.error) return <Failed error={tokens.error} retry={tokens.reload} />;
  if (hooks.error) return <Failed error={hooks.error} retry={hooks.reload} />;

  const makeToken = async (event) => {
    event.preventDefault();
    const form = event.target;
    const body = Object.fromEntries(new FormData(form));
    const done = await act(() => api('/tokens', { method: 'POST', body }), 'Token created.');
    if (done) { setShown({ title: 'Your new token. Copy it now; it is not shown again.', value: done.token }); form.reset(); }
  };
  const makeHook = async (event) => {
    event.preventDefault();
    const form = event.target;
    const data = new FormData(form);
    const body = { url: data.get('url'), events: data.getAll('events') };
    const done = await act(() => api('/webhooks', { method: 'POST', body }), 'Webhook added.');
    if (done) { setShown({ title: 'Signing secret for this webhook. Copy it now; it is not shown again.', value: done.secret }); form.reset(); }
  };
  const test = async (id) => {
    const done = await act(() => api(`/webhooks/${id}/test`, { method: 'POST' }));
    if (done) setShown({ title: `Test delivery answered`, value: done.status });
  };

  return (
    <>
      <PageHead title="Integrations" text="Let other systems read records, send changes to them, and check what they receive." />
      {shown && <ShownOnce {...shown} onClose={() => setShown(null)} />}

      <section className="panel">
        <h2>API tokens</h2>
        {tokens.data.items.length === 0 ? <Empty>No tokens yet.</Empty> : (
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Name</th><th>Access</th><th>Ends in</th><th>Last used</th><th>Status</th><th></th></tr></thead>
            <tbody>{tokens.data.items.map((t) => (
              <tr key={t.token_id}>
                <td>{t.name}</td><td>{t.scope}</td><td className="num">{t.hint}</td>
                <td className="num">{t.last_used ? t.last_used.slice(0, 16) : 'never'}</td>
                <td>{t.active ? <span className="badge badge--good">Active</span> : <span className="badge badge--bad">Revoked</span>}</td>
                <td>{t.active && <button className="link-btn" onClick={() => act(() => api(`/tokens/${t.token_id}`, { method: 'DELETE' }), 'Token revoked.')}>Revoke</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <form onSubmit={makeToken} style={{ marginTop: 'var(--space-md)' }}>
          <div className="row">
            <Field label="Name" id="tk-name"><input id="tk-name" name="name" placeholder="Court feed" required /></Field>
            <Field label="Access" id="tk-scope">
              <select id="tk-scope" name="scope" defaultValue="read">{tokens.data.scopes.map((s) => <option key={s}>{s}</option>)}</select>
            </Field>
            <button className="btn" type="submit">Create token</button>
          </div>
          <small className="muted">A token acts as you. Read tokens can only fetch. No token can manage users, tokens or webhooks.</small>
        </form>
      </section>

      <section className="panel">
        <h2>Webhooks</h2>
        {hooks.data.items.length === 0 ? <Empty>No webhooks yet.</Empty> : (
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Address</th><th>Events</th><th>Last delivery</th><th></th></tr></thead>
            <tbody>{hooks.data.items.map((h) => (
              <tr key={h.webhook_id}>
                <td style={{ overflowWrap: 'anywhere' }}>{h.url}</td>
                <td>{h.events.length ? h.events.join(', ') : 'all'}</td>
                <td>{h.last_status ? `${h.last_status} (${h.last_at.slice(0, 16)})` : 'none yet'}</td>
                <td>
                  <button className="link-btn" onClick={() => test(h.webhook_id)}>Test</button>{' '}
                  <button className="link-btn" onClick={() => act(() => api(`/webhooks/${h.webhook_id}`, { method: 'DELETE' }), 'Webhook removed.')}>Remove</button>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <form onSubmit={makeHook} style={{ marginTop: 'var(--space-md)' }}>
          <Field label="Address" id="wh-url" hint="Where to send changes. Must be https:// when the site is live."><input id="wh-url" name="url" placeholder="https://example.org/crms-hook" required /></Field>
          <fieldset style={{ border: 0, padding: 0, margin: 'var(--space-sm) 0' }}>
            <legend>Events (none ticked means all)</legend>
            {hooks.data.events.map((e) => (
              <label key={e} style={{ display: 'inline-flex', gap: 'var(--space-xs)', marginRight: 'var(--space-md)' }}>
                <input type="checkbox" name="events" value={e} style={{ width: 'auto' }} /> {e}
              </label>
            ))}
          </fieldset>
          <button className="btn" type="submit">Add webhook</button>
        </form>
      </section>

      <section className="panel">
        <h2>How another system uses this</h2>
        <p className="muted">Send the token in a header. Every call is read-only unless the token has write access.</p>
        <pre>{`curl -H "Authorization: Bearer crms_..." \\
  "${window.location.origin}/api/export/firs?since=2026-01-01"

curl -H "Authorization: Bearer crms_..." \\
  "${window.location.origin}/api/export/fir/42"`}</pre>
        <p className="muted">Each webhook call is a POST of JSON with the headers <code>X-CRMS-Event</code> and <code>X-CRMS-Signature</code>. The signature is <code>sha256=</code> and the HMAC-SHA256 of the raw body, keyed with the secret shown when the webhook was added. It carries ids, FIR number, status and category only; fetch the record with a token for anything more.</p>
        <pre>{`import hmac, hashlib
expected = "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
ok = hmac.compare_digest(expected, request.headers["X-CRMS-Signature"])`}</pre>
      </section>
    </>
  );
}
