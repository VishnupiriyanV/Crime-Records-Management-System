import { Link } from 'react-router-dom';
import { useTitle } from '../ui.jsx';
import { useT } from '../i18n.jsx';

export default function NotFound({ forbidden, message }) {
  const t = useT();
  const title = forbidden ? 'Not allowed' : 'Not found';
  useTitle(title);
  return (
    <div className="panel form-narrow">
      <h1>{t(title)}</h1>
      <p style={{ marginTop: 'var(--space-sm)' }}>
        {t(message || (forbidden ? 'Your role cannot open this page.' : 'That page does not exist.'))}
      </p>
      <p style={{ marginTop: 'var(--space-md)' }}><Link className="btn" to="/">{t('Back to start')}</Link></p>
    </div>
  );
}
