import { highlightParts } from '../../utils/text.js';

export function Highlight({ text, query }) {
  return (
    <>
      {highlightParts(text, query).map((p, i) => (p.hit ? <mark key={'h-' + i}>{p.text}</mark> : <span key={'h-' + i}>{p.text}</span>))}
    </>
  );
}

export function GlossaryTable({ entries, query }) {
  if (entries.length === 0) return null;
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead><tr><th scope="col">Term</th><th scope="col">Meaning</th></tr></thead>
        <tbody>
          {entries.map(([term, meaning]) => (
            <tr key={term}>
              <th scope="row"><Highlight text={term} query={query} /></th>
              <td><Highlight text={meaning} query={query} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
