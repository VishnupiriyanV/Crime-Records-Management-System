import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from './api.js';

const Session = createContext(null);
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
