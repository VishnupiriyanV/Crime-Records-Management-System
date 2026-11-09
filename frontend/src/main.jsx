import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import { LangProvider } from './i18n.jsx';
import { SessionProvider } from './session.jsx';
import './styles/app.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <LangProvider>
        <SessionProvider>
          <App />
        </SessionProvider>
      </LangProvider>
    </BrowserRouter>
  </StrictMode>,
);
