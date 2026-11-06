import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from './api.js';

const Session = createContext(null);
const POLL_MS = 10000;
export const useSession = () => useContext(Session);

export function SessionProvider({ children }) {
  const [state, setState] = useState({ user: null, unread: 0, ready: false });
  const [flash, setFlash] = useState(null);
  const location = useLocation();

  const refresh = useCallback(async () => {
    const data = await api('/auth/me').catch(() => ({ user: null, unread: 0 }));
    setState({ ...data, ready: true });
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // check for new alerts every so often while a signed-in tab is visible
  const lastUnread = useRef(0);
  useEffect(() => { lastUnread.current = state.unread; }, [state.unread]);
  useEffect(() => {
    if (!state.user) return undefined;
    const timer = setInterval(async () => {
      if (document.hidden) return;
      const data = await api('/auth/me').catch(() => null);
      if (!data || !data.user) return;
      if (data.unread > lastUnread.current) setFlash({ text: 'You have a new alert.', type: 'ok', keep: false });
      lastUnread.current = data.unread;
      setState((s) => ({ ...s, unread: data.unread }));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [state.user?.user_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // a message shown before a redirect (keep) survives one navigation, anything else goes at once
  useEffect(() => {
    setFlash((f) => (f && f.keep ? { ...f, keep: false } : null));
  }, [location.pathname]);

  const notice = useCallback((text, type = 'ok', keep = false) => setFlash({ text, type, keep }), []);

  return (
    <Session.Provider value={{ ...state, refresh, flash, notice, setSession: (d) => setState({ ...d, ready: true }) }}>
      {children}
    </Session.Provider>
  );
}
