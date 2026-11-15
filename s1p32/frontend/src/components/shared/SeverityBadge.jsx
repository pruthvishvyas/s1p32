const WORDS = { HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' };

export function SeverityBadge({ severity }) {
  const key = String(severity || 'LOW').toUpperCase();
  return <span className={'badge badge-' + key.toLowerCase()}>{WORDS[key] || 'Low'}</span>;
}
