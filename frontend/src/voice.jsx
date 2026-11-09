import { useEffect, useRef, useState } from 'react';
import { api } from './api';

// Chrome, Edge and Safari have this; Firefox does not, and there the buttons stay hidden
const Recognition = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

const LANGUAGES = [['en-IN', 'English'], ['ta-IN', 'Tamil'], ['hi-IN', 'Hindi']];

function savedLanguage() {
  try { return localStorage.getItem('crms-voice') || 'en-IN'; } catch { return 'en-IN'; }
}

function useLanguage() {
  const [lang, setLang] = useState(savedLanguage);
  const change = (value) => {
    setLang(value);
    try { localStorage.setItem('crms-voice', value); } catch { /* the choice just is not remembered */ }
  };
  return [lang, change];
}

function LanguagePick({ lang, onChange, id }) {
  return (
    <select id={id} className="voice-lang" aria-label="Spoken language" value={lang} onChange={(e) => onChange(e.target.value)}>
      {LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
    </select>
  );
}

// onText gets the finished words and the words still being worked out; onDone gets the finished words
function useListener(lang, onText, onDone) {
  const recognition = useRef(null);
  const [listening, setListening] = useState(false);
  const [problem, setProblem] = useState('');

  const start = () => {
    const r = new Recognition();
    let finished = '';
    r.lang = lang;
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (event) => {
      let rough = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) finished += `${piece} `;
        else rough += piece;
      }
      onText(finished.trim(), rough);
    };
    r.onerror = (event) => {
      if (event.error === 'not-allowed') setProblem('The microphone is blocked. Allow it in the address bar and try again.');
      else if (event.error !== 'no-speech' && event.error !== 'aborted') setProblem(`Voice input stopped (${event.error}).`);
    };
    r.onend = () => { setListening(false); onDone(finished.trim()); };
    recognition.current = r;
    setProblem('');
    setListening(true);
    r.start();
  };
  const stop = () => recognition.current?.stop();
  useEffect(() => () => recognition.current?.abort(), []);
  return { listening, problem, start, stop };
}

// a small mic button for one text box; what is said is added after what is already typed
export function Dictate({ target }) {
  const [lang, setLang] = useLanguage();
  const before = useRef('');
  const { listening, problem, start, stop } = useListener(
    lang,
    (done, rough) => {
      const box = document.getElementById(target);
      if (box) box.value = [before.current, done, rough].filter(Boolean).join(' ');
    },
    () => {},
  );
  if (!Recognition) return null;

  const toggle = () => {
    if (listening) return stop();
    before.current = document.getElementById(target)?.value.trim() || '';
    start();
  };
  return (
    <div className="voice-row">
      <button type="button" className={`btn btn--small${listening ? ' btn--danger' : ''}`} onClick={toggle}>
        {listening ? 'Stop' : 'Dictate'}
      </button>
      <LanguagePick id={`lang-${target}`} lang={lang} onChange={setLang} />
      <small className="muted">Uses your browser's speech service.</small>
      {problem && <small className="voice-problem">{problem}</small>}
    </div>
  );
}

// fills a form field without touching anything the person already typed
function fillEmpty(id, value, empty = '') {
  const box = document.getElementById(id);
  if (!box || !value || (box.value || '').trim() !== empty) return null;
  box.value = value;
  return box;
}

// speak the whole complaint once; the server sorts the words into the form
export function SpeakComplaint() {
  const [lang, setLang] = useLanguage();
  const [heard, setHeard] = useState('');
  const [result, setResult] = useState('');
  const english = lang.startsWith('en');

  const { listening, problem, start, stop } = useListener(
    lang,
    (done, rough) => setHeard([done, rough].filter(Boolean).join(' ')),
    async (done) => {
      if (!done) return;
      try {
        const got = await api('/complaints/dictation', { method: 'POST', body: { text: done } });
        const filled = [];
        if (fillEmpty('description', got.description)) filled.push('what happened');
        if (fillEmpty('title', got.title)) filled.push('title');
        if (fillEmpty('location', got.location)) filled.push('place');
        if (fillEmpty('incident_date', got.incident_date)) filled.push('date');
        if (got.category && got.category !== 'Other' && fillEmpty('category', got.category, 'Other')) filled.push('category');
        setResult(filled.length
          ? `Filled from your voice: ${filled.join(', ')}. Check every field before you submit.`
          : 'Nothing was filled because those boxes already have text.');
      } catch (err) {
        setResult(`Could not read that: ${err.message}`);
      }
    },
  );
  if (!Recognition) return null;

  const toggle = () => {
    if (listening) return stop();
    setHeard('');
    setResult('');
    start();
  };
  return (
    <div className="voice-panel" aria-live="polite">
      <div className="voice-row">
        <button type="button" className={`btn${listening ? ' btn--danger' : ' btn--primary'}`} onClick={toggle}>
          {listening ? 'Stop and fill the form' : 'Speak your complaint'}
        </button>
        <LanguagePick id="voice-lang" lang={lang} onChange={setLang} />
      </div>
      <small className="muted">
        Say what happened, where and when. Your browser's speech service turns it into text, and it may send the audio to its maker.
        {!english && ' Tamil and Hindi are written out as you speak them, but only English is sorted into the category, date and place.'}
      </small>
      {heard && <p className="voice-heard">{heard}</p>}
      {problem && <p className="voice-problem">{problem}</p>}
      {result && <p className="voice-result">{result}</p>}
    </div>
  );
}
