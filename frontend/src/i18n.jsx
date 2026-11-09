import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import hi from './lang/hi.js';
import ta from './lang/ta.js';

// the English text is the key, so a string with no translation simply shows in English
const BOOKS = { en: {}, ta, hi };
export const LANGUAGES = [['en', 'English'], ['ta', 'தமிழ்'], ['hi', 'हिन्दी']];

const Lang = createContext({ lang: 'en', setLang: () => {}, t: (text) => text });

function saved() {
  try {
    const lang = localStorage.getItem('crms-lang');
    return lang in BOOKS ? lang : 'en';
  } catch { return 'en'; }
}

function fill(text, vars) {
  return vars ? text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? `{${name}}`)) : text;
}

// the server writes alerts in English with the title or status inside; match the template and translate around it
function fromTemplate(book, text) {
  for (const [key, value] of Object.entries(book)) {
    if (!key.includes('{')) continue;
    const names = [];
    const pattern = key.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{(\w+)\}/g, (_, name) => { names.push(name); return '(.+?)'; });
    const found = new RegExp(`^${pattern}$`).exec(text);
    if (found) return fill(value, Object.fromEntries(names.map((name, i) => [name, book[found[i + 1]] ?? found[i + 1]])));
  }
  return null;
}

export function LangProvider({ children }) {
  const [lang, setLang] = useState(saved);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const change = useCallback((next) => {
    setLang(next);
    try { localStorage.setItem('crms-lang', next); } catch { /* the choice just is not remembered */ }
  }, []);
  const t = useCallback((text, vars) => {
    if (typeof text !== 'string') return text;
    const book = BOOKS[lang];
    return fill(book[text] ?? (lang === 'en' ? null : fromTemplate(book, text)) ?? text, vars);
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang: change, t }), [lang, change, t]);
  return <Lang.Provider value={value}>{children}</Lang.Provider>;
}

export const useT = () => useContext(Lang).t;
export const useLang = () => useContext(Lang);
