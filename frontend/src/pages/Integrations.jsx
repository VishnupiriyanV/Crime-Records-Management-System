import { useState } from 'react';
import { api } from '../api.js';
import { Empty, Failed, Field, Loading, PageHead, useAct, useLoad } from '../ui.jsx';
import { useT } from '../i18n.jsx';

// a secret that is shown once; after this the server only keeps a hash (tokens) or hands nothing back (webhooks)
function ShownOnce({ title, value, onClose }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); } catch { /* the text is selectable instead */ }
  };
  return (
    <div className="voice-panel" role="status">
      <b>{t(title)}</b>
      <code style={{ overflowWrap: 'anywhere', userSelect: 'all' }}>{value}</code>
      <div className="voice-row">
        <button type="button" className="btn btn--small" onClick={copy}>{t(copied ? 'Copied' : 'Copy')}</button>
        <button type="button" className="btn btn--small" onClick={onClose}>{t('I have saved it')}</button>
      </div>
    </div>
  );
}

export function Integrations() {
  const t = useT();
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
      <PageHead title={t('Integrations')} text="Let other systems read records, send changes to them, and check what they receive." />
      {shown && <ShownOnce {...shown} onClose={() => setShown(null)} />}

      <section className="panel">
        <h2>{t('API tokens')}</h2>
        {tokens.data.items.length === 0 ? <Empty>{t('No tokens yet.')}</Empty> : (
          <div className="table-wrap"><table className="data">
            <thead><tr><th>{t('Name')}</th><th>{t('Access')}</th><th>{t('Ends in')}</th><th>{t('Last used')}</th><th>{t('Status')}</th><th></th></tr></thead>
            <tbody>{tokens.data.items.map((k) => (
              <tr key={k.token_id}>
                <td>{k.name}</td><td>{t(k.scope)}</td><td className="num">{k.hint}</td>
                <td className="num">{k.last_used ? k.last_used.slice(0, 16) : t('never')}</td>
                <td>{k.active ? <span className="badge badge--good">{t('Active')}</span> : <span className="badge badge--bad">{t('Revoked')}</span>}</td>
                <td>{k.active && <button className="link-btn" onClick={() => act(() => api(`/tokens/${k.token_id}`, { method: 'DELETE' }), 'Token revoked.')}>{t('Revoke')}</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <form onSubmit={makeToken} style={{ marginTop: 'var(--space-md)' }}>
          <div className="row">
            <Field label="Name" id="tk-name"><input id="tk-name" name="name" placeholder={t('Court feed')} required /></Field>
            <Field label="Access" id="tk-scope">
              <select id="tk-scope" name="scope" defaultValue="read">{tokens.data.scopes.map((s) => <option key={s} value={s}>{t(s)}</option>)}</select>
            </Field>
            <button className="btn" type="submit">{t('Create token')}</button>
          </div>
          <small className="muted">{t('A token acts as you. Read tokens can only fetch. No token can manage users, tokens or webhooks.')}</small>
        </form>
      </section>

      <section className="panel">
        <h2>{t('Webhooks')}</h2>
        {hooks.data.items.length === 0 ? <Empty>{t('No webhooks yet.')}</Empty> : (
          <div className="table-wrap"><table className="data">
            <thead><tr><th>{t('Address')}</th><th>{t('Events')}</th><th>{t('Last delivery')}</th><th></th></tr></thead>
            <tbody>{hooks.data.items.map((h) => (
              <tr key={h.webhook_id}>
                <td style={{ overflowWrap: 'anywhere' }}>{h.url}</td>
                <td>{h.events.length ? h.events.map((e) => t(e)).join(', ') : t('all')}</td>
                <td>{h.last_status ? `${h.last_status} (${h.last_at.slice(0, 16)})` : t('none yet')}</td>
                <td>
                  <button className="link-btn" onClick={() => test(h.webhook_id)}>{t('Test')}</button>{' '}
                  <button className="link-btn" onClick={() => act(() => api(`/webhooks/${h.webhook_id}`, { method: 'DELETE' }), 'Webhook removed.')}>{t('Remove')}</button>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <form onSubmit={makeHook} style={{ marginTop: 'var(--space-md)' }}>
          <Field label="Address" id="wh-url" hint="Where to send changes. Must be https:// when the site is live."><input id="wh-url" name="url" placeholder={t('https://example.org/crms-hook')} required /></Field>
          <fieldset style={{ border: 0, padding: 0, margin: 'var(--space-sm) 0' }}>
            <legend>{t('Events (none ticked means all)')}</legend>
            {hooks.data.events.map((e) => (
              <label key={e} style={{ display: 'inline-flex', gap: 'var(--space-xs)', marginRight: 'var(--space-md)' }}>
                <input type="checkbox" name="events" value={e} style={{ width: 'auto' }} /> {e}
              </label>
            ))}
          </fieldset>
          <button className="btn" type="submit">{t('Add webhook')}</button>
        </form>
      </section>

      <section className="panel">
        <h2>{t('How another system uses this')}</h2>
        <p className="muted">{t('Send the token in a header. Every call is read-only unless the token has write access.')}</p>
        <pre>{`curl -H "Authorization: Bearer crms_..." \\
  "${window.location.origin}/api/export/firs?since=2026-01-01"

curl -H "Authorization: Bearer crms_..." \\
  "${window.location.origin}/api/export/fir/42"`}</pre>
        <p className="muted">{t('Each webhook call is a POST of JSON with the headers')}{' '}<code>X-CRMS-Event</code>{' '}{t('and')}{' '}<code>X-CRMS-Signature</code>{t('. The signature is')}{' '}<code>sha256=</code>{' '}{t('and the HMAC-SHA256 of the raw body, keyed with the secret shown when the webhook was added. It carries ids, FIR number, status and category only; fetch the record with a token for anything more.')}</p>
        <pre>{`import hmac, hashlib
expected = "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
ok = hmac.compare_digest(expected, request.headers["X-CRMS-Signature"])`}</pre>
      </section>
    </>
  );
}
