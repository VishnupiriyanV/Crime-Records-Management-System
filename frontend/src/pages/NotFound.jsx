import { Link } from 'react-router-dom';
import { useTitle } from '../ui.jsx';

export default function NotFound({ forbidden, message }) {
  const title = forbidden ? 'Not allowed' : 'Not found';
  useTitle(title);
  return (
    <div className="panel form-narrow">
      <h1>{title}</h1>
      <p style={{ marginTop: 'var(--space-sm)' }}>
        {message || (forbidden ? 'Your role cannot open this page.' : 'That page does not exist.')}
      </p>
      <p style={{ marginTop: 'var(--space-md)' }}><Link className="btn" to="/">Back to start</Link></p>
    </div>
  );
}
