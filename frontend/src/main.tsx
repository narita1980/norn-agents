import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';

// #region agent log
fetch('http://127.0.0.1:7404/ingest/25e6a887-4597-472d-88ac-ee336bd2fb9e', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': 'f24819' },
  body: JSON.stringify({
    sessionId: 'f24819',
    runId: 'pre-fix-analysis',
    hypothesisId: 'B',
    location: 'main.tsx:boot',
    message: 'SPA boot',
    data: {
      apiBase: import.meta.env.VITE_API_BASE_URL ?? '',
      path: window.location.pathname,
    },
    timestamp: Date.now(),
  }),
}).catch(() => {});
// #endregion

const container = document.getElementById('root');
if (!container) {
  throw new Error('root element not found');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
