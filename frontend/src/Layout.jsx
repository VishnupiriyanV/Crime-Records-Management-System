import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from './api.js';
import { useSession } from './session.jsx';

const links = {
  citizen: [['/complaints', 'My complaints'], ['/complaints/new', 'File a complaint'], ['/records', 'Public records']],
  officer: [['/dashboard', 'Dashboard'], ['/complaints', 'Complaints'], ['/cases', 'Cases'], ['/criminals', 'Criminals']],
  admin: [['/dashboard', 'Dashboard'], ['/complaints', 'Complaints'], ['/cases', 'Cases'], ['/criminals', 'Criminals'], ['/reports', 'Reports'], ['/users', 'Users']],
};

export default function Layout() {
  const { user, unread, flash, setSession } = useSession();
  const navigate = useNavigate();

  async function signOut() {
    await api('/auth/logout', { method: 'POST' });
    setSession({ user: null, unread: 0 });
    navigate('/login');
  }

  return (
    <>
      <header className="top">
        <div className="shell">
          <Link className="brand" to="/">CRMS</Link>
          {user && (
            <>
              <nav className="nav" aria-label="Main">
                {links[user.role].map(([to, label]) => (
                  <NavLink key={to} to={to} end={to === '/complaints'}>{label}</NavLink>
                ))}
              </nav>
              <div className="who">
                <Link className="bell" to="/notifications">Alerts{unread > 0 && <b>{unread}</b>}</Link>
                <Link to="/profile">{user.name}</Link>
                <button className="link-btn" onClick={signOut}>Sign out</button>
              </div>
            </>
          )}
        </div>
      </header>
      <main>
        <div className="shell">
          {flash && <div className={`flash ${flash.type === 'error' ? 'flash--error' : ''}`} role={flash.type === 'error' ? 'alert' : 'status'}>{flash.text}</div>}
          <Outlet />
        </div>
      </main>
      <footer><div className="shell">Crime Records Management System, DBMS lab project</div></footer>
    </>
  );
}
