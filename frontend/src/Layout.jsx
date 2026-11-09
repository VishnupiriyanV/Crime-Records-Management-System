import { Fragment, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from './api.js';
import { useSession } from './session.jsx';

const links = {
  citizen: [['/complaints', 'My complaints'], ['/complaints/new', 'File a complaint'], ['/records', 'Public records']],
  officer: [['/dashboard', 'Dashboard'], ['/complaints', 'Complaints'], ['/cases', 'Cases'], ['/criminals', 'Criminals'], ['/map', 'Map'], ['/stations', 'Stations']],
  admin: [['/dashboard', 'Dashboard'], ['/complaints', 'Complaints'], ['/cases', 'Cases'], ['/criminals', 'Criminals'], ['/map', 'Map'], ['/stations', 'Stations'], ['/reports', 'Reports'], ['/users', 'Users'], ['/audit', 'Audit'], ['/integrations', 'Integrations']],
};

// press g, then one of these keys, to jump to a page
const jumps = {
  citizen: { c: '/complaints', n: '/complaints/new', r: '/records', a: '/notifications' },
  officer: { d: '/dashboard', c: '/complaints', k: '/cases', r: '/criminals', m: '/map', s: '/stations', a: '/notifications' },
  admin: { d: '/dashboard', c: '/complaints', k: '/cases', r: '/criminals', m: '/map', s: '/stations', p: '/reports', u: '/users', l: '/audit', i: '/integrations', a: '/notifications' },
};
const jumpLabels = {
  d: 'Dashboard', c: 'Complaints', k: 'Cases', r: 'Criminals (Public records for citizens)', p: 'Reports',
  u: 'Users', l: 'Audit log', i: 'Integrations', m: 'Map', s: 'Stations', a: 'Alerts', n: 'File a complaint',
};

function isDark() {
  const set = document.documentElement.dataset.theme;
  if (set) return set === 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export default function Layout() {
  const [dark, setDark] = useState(isDark);
  const { user, unread, flash, setSession } = useSession();
  const navigate = useNavigate();
  const searchBox = useRef(null);
  const help = useRef(null);

  useEffect(() => {
    if (!user) return undefined;
    let waiting = false;
    let timer;
    const onKey = (e) => {
      const tag = e.target.tagName;
      if (e.ctrlKey || e.metaKey || e.altKey || ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || e.target.isContentEditable) return;
      if (waiting) {
        waiting = false;
        clearTimeout(timer);
        const to = jumps[user.role][e.key];
        if (to) { e.preventDefault(); navigate(to); }
        return;
      }
      if (e.key === '/') { e.preventDefault(); searchBox.current?.focus(); }
      else if (e.key === '?') help.current?.showModal();
      else if (e.key === 'g') { waiting = true; timer = setTimeout(() => { waiting = false; }, 1200); }
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); clearTimeout(timer); };
  }, [user, navigate]);

  function search(event) {
    event.preventDefault();
    const q = new FormData(event.target).get('q').trim();
    if (q) navigate(`/search?q=${encodeURIComponent(q)}`);
  }

  function toggleTheme() {
    const next = dark ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('crms-theme', next); } catch (e) {}
    setDark(!dark);
  }

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
              <form className="search" role="search" onSubmit={search}>
                <input ref={searchBox} name="q" type="search" placeholder="Search ( / )" aria-label="Search" autoComplete="off" />
              </form>
              <div className="who">
                <Link className="bell" to="/notifications">Alerts{unread > 0 && <b>{unread}</b>}</Link>
                <Link to="/profile">{user.name}</Link>
                <button className="link-btn" onClick={signOut}>Sign out</button>
              </div>
            </>
          )}
          <button className="link-btn theme-btn" onClick={toggleTheme} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
            {dark ? 'Light' : 'Dark'}
          </button>
        </div>
      </header>
      <main>
        <div className="shell">
          {flash && <div className={`flash ${flash.type === 'error' ? 'flash--error' : ''}`} role={flash.type === 'error' ? 'alert' : 'status'}>{flash.text}</div>}
          <Outlet />
        </div>
      </main>
      <footer>
        <div className="shell">
          Crime Records Management System, DBMS lab project
          {user && <button className="link-btn" onClick={() => help.current?.showModal()}>Keyboard shortcuts</button>}
        </div>
      </footer>
      <dialog ref={help} className="preview help" onClick={(e) => e.target === help.current && help.current.close()}>
        <div className="preview-head"><b>Keyboard shortcuts</b><button className="link-btn" onClick={() => help.current.close()}>Close</button></div>
        {user && (
          <dl className="facts">
            <dt><kbd>/</kbd></dt><dd>Search</dd>
            <dt><kbd>?</kbd></dt><dd>Show this list</dd>
            {Object.keys(jumps[user.role]).map((k) => (
              <Fragment key={k}><dt><kbd>g</kbd> <kbd>{k}</kbd></dt><dd>{user.role === 'citizen' && k === 'r' ? 'Public records' : jumpLabels[k]}</dd></Fragment>
            ))}
          </dl>
        )}
      </dialog>
    </>
  );
}
