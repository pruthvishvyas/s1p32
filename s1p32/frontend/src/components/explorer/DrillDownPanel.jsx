import { useEffect, useRef } from 'react';
import { Icon } from '../shared/Icon.jsx';

export function DrillDownPanel({ title, onClose, children }) {
  const ref = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const previous = document.activeElement;
    const node = ref.current;
    if (node) node.focus();
    const onKey = e => {
      if (e.key === 'Escape') { closeRef.current(); return; }
      if (e.key !== 'Tab' || !node) return;
      const items = node.querySelectorAll('button, a[href], input, select, textarea');
      if (items.length === 0) { e.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === node)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (previous && previous.focus) previous.focus();
    };
  }, []);

  return (
    <div className="drill-backdrop" onClick={() => closeRef.current()}>
      <aside className="drill-panel" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref} onClick={e => e.stopPropagation()}>
        <header className="drill-head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn" onClick={() => closeRef.current()} aria-label="Close details"><Icon name="close" /></button>
        </header>
        <div className="drill-body">{children}</div>
        <p className="muted small">Figures are aggregated; no individual records are shown.</p>
      </aside>
    </div>
  );
}
