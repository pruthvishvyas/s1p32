export function refreshHint() {
  const dev = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.DEV;
  return dev
    ? 'In the backend folder run main.py and then export_for_frontend.py, then run npm run check in this folder.'
    : 'The analysis data for this section was not published with this site. Run the backend steps again and publish a new version.';
}

export function truncate(value, max) {
  const s = String(value === null || value === undefined ? '' : value);
  return s.length > max ? s.slice(0, Math.max(1, max - 1)) + '\u2026' : s;
}

export function pluralize(word) {
  const w = String(word);
  if (/[^aeiou]y$/i.test(w)) return w.slice(0, -1) + 'ies';
  if (/(s|x|z|ch|sh)$/i.test(w)) return w + 'es';
  return w + 's';
}

// Splits text so a search match can be wrapped in a mark element
export function highlightParts(text, query) {
  const s = String(text === null || text === undefined ? '' : text);
  const q = String(query || '').trim();
  if (!q) return [{ text: s, hit: false }];
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pieces = s.split(new RegExp('(' + escaped + ')', 'gi'));
  return pieces.filter(p => p !== '').map(p => ({ text: p, hit: p.toLowerCase() === q.toLowerCase() }));
}
