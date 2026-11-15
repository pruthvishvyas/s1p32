import { useId, useState } from 'react';
import { useDataset, useDataFile } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { adaptSimulation } from '../../utils/adapters.js';
import { dataPath } from '../../utils/datasets.js';
import { interpolate } from '../../utils/sim.js';

export function WhatIfSimulator() {
  const query = useDataset('simulations');
  if (query.loading || query.error) {
    return <DataState query={query} label="what-if scenarios" skeleton={<SkeletonCard count={2} height={160} />} />;
  }
  if (query.data.length === 0) return <div className="card state-box"><p>No what-if scenarios were produced for this project.</p></div>;
  return <SimulatorBody index={query.data} />;
}

function SimulatorBody({ index }) {
  const pickerId = useId();
  const [chosen, setChosen] = useState(index[0].id);
  const entry = index.find(i => i.id === chosen) || index[0];
  return (
    <div className="stack">
      <div className="field">
        <label htmlFor={pickerId}>Scenario</label>
        <select id={pickerId} value={entry.id} onChange={e => setChosen(e.target.value)}>
          {index.map(i => <option key={i.id} value={i.id}>{i.title}</option>)}
        </select>
      </div>
      <SimulationView key={entry.id} entry={entry} />
    </div>
  );
}

function SimulationView({ entry }) {
  const query = useDataFile(dataPath(entry.file), adaptSimulation);
  if (query.loading || query.error) {
    return <DataState query={query} label="scenario" skeleton={<SkeletonCard count={2} height={160} />} />;
  }
  return <SimulationBody sim={query.data} />;
}

function SimulationBody({ sim }) {
  const fmt = useFormat();
  const sliderId = useId();
  const v = sim.variable;
  const [x, setX] = useState(v.default);
  const base = interpolate(sim.table, v.default);
  const scenario = interpolate(sim.table, x);
  const shownX = fmt.value(x, v.format) + (v.unit && v.format !== 'percent' && v.format !== 'currency' ? ' ' + v.unit : '');
  return (
    <div className="stack">
      <section className="card">
        <h3>{sim.title}</h3>
        {sim.description ? <p className="muted">{sim.description}</p> : null}
        <div className="field">
          <label htmlFor={sliderId}>{v.label + ': ' + shownX}</label>
          <input id={sliderId} type="range" min={v.min} max={v.max} step={v.step} value={x} onChange={e => setX(Number(e.target.value))} />
          <p className="muted small">{'Range ' + fmt.value(v.min, v.format) + ' to ' + fmt.value(v.max, v.format) + '. Starting point ' + fmt.value(v.default, v.format) + '.'}</p>
        </div>
        <button type="button" className="btn-secondary" onClick={() => setX(v.default)}>Reset</button>
      </section>
      <div className="card table-card">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr><th scope="col">Measure</th><th scope="col">Baseline</th><th scope="col">Scenario</th><th scope="col">Difference</th></tr>
            </thead>
            <tbody>
              {sim.outputs.map(o => {
                const b = base ? base[o.key] : null;
                const s = scenario ? scenario[o.key] : null;
                const diff = b !== null && b !== undefined && s !== null && s !== undefined ? s - b : null;
                return (
                  <tr key={o.key}>
                    <th scope="row">{o.label}</th>
                    <td>{fmt.value(b, o.format)}</td>
                    <td>{fmt.value(s, o.format)}</td>
                    <td>{diff === null ? '-' : (diff > 0 ? '+' : '') + fmt.value(diff, o.format)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      {sim.assumptions.length > 0 ? (
        <section className="card">
          <h3>Assumptions</h3>
          <ul className="plain-list">
            {sim.assumptions.map((a, i) => <li key={'a-' + i}>{a}</li>)}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
