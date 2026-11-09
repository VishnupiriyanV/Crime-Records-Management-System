import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { useSession } from '../session.jsx';
import { Field, formData, useTitle } from '../ui.jsx';
import { useT } from '../i18n.jsx';

function useSignIn(path) {
  const { setSession } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState('');

  async function submit(event) {
    const body = formData(event);
    try {
      const session = await api(path, { method: 'POST', body });
      setSession(session);
      const next = params.get('next');
      const safe = next && next.startsWith('/') && !next.startsWith('//');
      navigate(safe ? next : session.user.role === 'citizen' ? '/complaints' : '/dashboard');
    } catch (err) {
      setError(err.message);
    }
  }
  return { submit, error };
}

export function Login() {
  const t = useT();
  useTitle('Sign in');
  const { submit, error } = useSignIn('/auth/login');
  return (
    <div className="auth">
      <h1>{t('Sign in')}</h1>
      <form className="panel" onSubmit={submit}>
        {error && <div className="flash flash--error" role="alert">{t(error)}</div>}
        <Field label="Email" id="email"><input id="email" name="email" type="email" autoComplete="username" required autoFocus /></Field>
        <Field label="Password" id="password"><input id="password" name="password" type="password" autoComplete="current-password" required /></Field>
        <button className="btn btn--primary" type="submit">{t('Sign in')}</button>
        <p className="alt">{t('New here?')} <Link to="/register">{t('Create a citizen account')}</Link></p>
      </form>
    </div>
  );
}

export function Register() {
  const t = useT();
  useTitle('Create account');
  const { submit, error } = useSignIn('/auth/register');
  return (
    <div className="auth">
      <h1>{t('Create account')}</h1>
      <form className="panel" onSubmit={submit}>
        {error && <div className="flash flash--error" role="alert">{t(error)}</div>}
        <Field label="Full name" id="name"><input id="name" name="name" autoComplete="name" required autoFocus /></Field>
        <Field label="Email" id="email"><input id="email" name="email" type="email" autoComplete="email" required /></Field>
        <Field label="Password" id="password" hint="At least 8 characters.">
          <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
        </Field>
        <button className="btn btn--primary" type="submit">{t('Create account')}</button>
        <p className="alt">{t('Already registered?')} <Link to="/login">{t('Sign in')}</Link></p>
      </form>
    </div>
  );
}
