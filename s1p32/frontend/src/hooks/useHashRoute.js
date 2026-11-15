import { useCallback, useEffect, useState } from 'react';

function readHash() {
  return window.location.hash.replace(/^#\/?/, '');
}

export function useHashRoute(valid, fallback) {
  const [raw, setRaw] = useState(readHash);
  useEffect(() => {
    const onChange = () => setRaw(readHash());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  const route = valid.includes(raw) ? raw : fallback;
  const go = useCallback(id => { window.location.hash = '/' + id; }, []);
  return [route, go];
}
