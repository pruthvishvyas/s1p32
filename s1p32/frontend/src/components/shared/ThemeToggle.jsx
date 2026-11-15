import { useState } from 'react';
import { Icon } from './Icon.jsx';

export function ThemeToggle() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute('data-theme') || 'light');
  const flip = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch { /* storage may be blocked; the choice still applies for this visit */ }
    setTheme(next);
  };
  return (
    <button type="button" className="icon-btn" onClick={flip} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  );
}
