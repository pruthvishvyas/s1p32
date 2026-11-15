import { useMemo, useState, useId } from 'react';
import { useContract } from '../../hooks/useContract.js';
import { useTerm } from '../../context/TerminologyContext.jsx';
import { GlossaryTable, Highlight } from './GlossaryTable.jsx';

function buildSections(term, project) {
  const revenue = term('revenue', { lower: true });
  const records = term('transaction', { plural: true, lower: true });
  const products = term('product', { plural: true, lower: true });
  const customers = term('customer', { plural: true, lower: true });
  return [
    { id: 'start', title: 'How to use this dashboard', body: [
      'The dashboard has three parts. Understand shows what is happening: key numbers, charts, groups of similar ' + records + ' and unusual records.',
      'Decide turns that into action: findings ranked by importance, a short list of recommended actions, a what-if tool and your goals.',
      'Monitor keeps watch: a forecast, a prediction form, progress against goals and active alerts. Explore lets you slice the numbers yourself, and Data health shows how fresh the data is.',
      'This dashboard covers ' + (project.domain || 'your data') + ', with ' + products + ' and ' + customers + ' as the main groupings and ' + revenue + ' where money is involved.',
    ] },
    { id: 'overview', title: 'Overview', body: [
      'What you see: the key numbers at the top and a set of charts below. Each chart has a title and the question it answers.',
      'What it means: a key number is the latest value of a measure. A small arrow shows the change against the previous period.',
      'What to do: start with the numbers that moved most, then read the chart that explains them.',
    ] },
    { id: 'charts', title: 'How to read the charts', body: [
      'Bar chart: one bar per group; taller means a larger value. Long names are shortened and shown in full when you hover.',
      'Line chart: a value over time; look for direction and sudden jumps.',
      'Histogram: bars show how many records fall in each range, so you can see the usual spread and the extremes.',
      'Scatter chart: each dot is a record; a cloud rising from left to right means the two measures move together.',
      'Heat map: darker cells hold larger values. Hover a cell to read it.',
    ] },
    { id: 'segments', title: 'Segments', body: [
      'What you see: groups of similar ' + records + ', each with a size, a share of the total and a short description.',
      'What it means: members of a group behave alike, so one action usually suits the whole group.',
      'What to do: open a group to see its typical values, then compare it with the others.',
    ] },
    { id: 'anomalies', title: 'Anomalies', body: [
      'What you see: a table of unusual records. An anomaly is an unusual day or record that does not match normal behavior.',
      'What it means: the score shows how unusual it is; a higher score is more unusual. The reason says why it was flagged.',
      'What to do: sort by score, check the top rows first and decide if they are errors or real events.',
    ] },
    { id: 'severity', title: 'Severity and priority levels', body: [
      'High means act soon, Medium means plan for it, Low means keep in mind.',
      'Recommendations use four levels: Urgent, High, Medium and Routine. Start at the top.',
    ] },
    { id: 'insights', title: 'Insights and recommendations', body: [
      'What you see: findings with the evidence behind them and the action to take this week, then a prioritised action list.',
      'What it means: every finding comes from the data in this dashboard; the evidence line shows the numbers.',
      'What to do: filter by severity and work from the most important item down.',
    ] },
    { id: 'whatif', title: 'The what-if tool', body: [
      'What you see: a scenario picker, a slider and a table comparing the baseline with your scenario.',
      'What it means: moving the slider reads along a pre-computed table, so results between points are straight-line estimates.',
      'What to do: try the range end points and note the assumptions listed under the table.',
    ] },
    { id: 'goals', title: 'Goals and progress', body: [
      'Goals can have a fixed target or one you enter yourself. Targets you enter are saved on this device only and are never sent anywhere.',
      'Progress compares the latest actual value with the target and labels it On track, At risk, Off track or No target.',
    ] },
    { id: 'forecast', title: 'Forecast', body: [
      'A forecast is an estimate of the future based on past patterns. The shaded band, when shown, is the likely range.',
      'The typical error is how far off the forecast was when tested on recent history it had not seen. The baseline is a simple rule used as a yardstick; a good forecast beats it.',
      'This is a forecast, not a guarantee.',
    ] },
    { id: 'predict', title: 'Predict', body: [
      'Enter details in the form and press Predict. The estimate is worked out in your browser from patterns in past ' + records + '; nothing you type is stored or sent.',
      'For yes or no outcomes the result is a likelihood from 0 to 100 with a risk level. A caution appears if a value is outside the range seen in the data.',
    ] },
    { id: 'explore', title: 'Explore', body: [
      'Use the filter bar to choose a metric, a date range and groups. Click a bar in any chart to filter every other chart; click it again to clear.',
      'Copy summary puts the filtered totals on your clipboard as plain text.',
      'Figures are aggregated; no individual records are shown.',
    ] },
    { id: 'health', title: 'Data health', body: [
      'This page shows when the analysis last ran, how many rows it used, which steps succeeded and which files are available. If a section is empty, look here first.',
    ] },
  ];
}

const GLOSSARY = [
  ['Anomaly', 'An unusual day or record that does not match normal behavior.'],
  ['Forecast', 'An estimate of the future based on past patterns.'],
  ['Held-out error', 'How far off the forecast was when tested on recent history it had not seen.'],
  ['Baseline', 'A simple rule used as a yardstick.'],
  ['Segment', 'A group of records that behave alike.'],
  ['Score', 'How unusual a flagged record is; higher means more unusual.'],
  ['Risk level', 'A plain label for how likely the outcome is: Low, Medium or High.'],
  ['Aggregated', 'Added up into groups so no single record can be identified.'],
];

export function UserManual() {
  const contract = useContract();
  const term = useTerm();
  const searchId = useId();
  const [query, setQuery] = useState('');
  const project = contract.data ? contract.data.project : { domain: '' };
  const sections = useMemo(() => buildSections(term, project), [term, project]);
  const q = query.trim().toLowerCase();
  const shown = q ? sections.filter(s => (s.title + ' ' + s.body.join(' ')).toLowerCase().includes(q)) : sections;
  const glossary = q ? GLOSSARY.filter(([t, m]) => (t + ' ' + m).toLowerCase().includes(q)) : GLOSSARY;
  return (
    <div className="stack manual">
      <div className="manual-tools">
        <div className="field">
          <label htmlFor={searchId}>Search the guide</label>
          <input id={searchId} type="search" value={query} onChange={e => setQuery(e.target.value)} />
        </div>
        <button type="button" className="btn-secondary" onClick={() => window.print()}>Print</button>
      </div>
      {shown.length === 0 && glossary.length === 0 ? <div className="card state-box"><p>Nothing in the guide matches that search.</p></div> : null}
      {shown.map(s => (
        <section className="card" key={s.id}>
          <h2><Highlight text={s.title} query={query} /></h2>
          {s.body.map((p, i) => <p key={s.id + '-' + i}><Highlight text={p} query={query} /></p>)}
        </section>
      ))}
      {glossary.length > 0 ? (
        <section className="card">
          <h2>Glossary</h2>
          <GlossaryTable entries={glossary} query={query} />
        </section>
      ) : null}
    </div>
  );
}
