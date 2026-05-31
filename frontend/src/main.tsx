import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ApiAuthGate } from './components/ApiAuthGate';
import './styles.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('root element not found');
}

createRoot(container).render(
  <StrictMode>
    <ApiAuthGate>
      <App />
    </ApiAuthGate>
  </StrictMode>,
);
