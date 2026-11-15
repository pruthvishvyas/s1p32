import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { useChartColors } from '../../hooks/useChartColors.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { truncate } from '../../utils/text.js';

function tipStyle(colors) {
  return { background: colors.surface, border: '1px solid ' + colors.grid, color: colors.textPrimary, borderRadius: '0.5rem' };
}

function tickProps(colors) {
  return { fill: colors.text, fontSize: 12 };
}

export function BarBlock({ rows, selected, onSelect, format, histogram, name }) {
  const colors = useChartColors();
  const fmt = useFormat();
  const long = !histogram && rows.some(r => String(r.label).length > 14);
  const pick = d => {
    const label = d && d.payload ? d.payload.label : d && d.label;
    if (onSelect && label !== undefined) onSelect(label);
  };
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={rows} layout={long ? 'vertical' : 'horizontal'} barCategoryGap={histogram ? 0 : '20%'} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
        {long ? (
          <XAxis type="number" tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        ) : (
          <XAxis dataKey="label" tickFormatter={v => truncate(v, 14)} tick={tickProps(colors)} stroke={colors.grid} interval="preserveStartEnd" minTickGap={8} />
        )}
        {long ? (
          <YAxis type="category" dataKey="label" width={120} tickFormatter={v => truncate(v, 14)} tick={tickProps(colors)} stroke={colors.grid} />
        ) : (
          <YAxis tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        )}
        <Tooltip contentStyle={tipStyle(colors)} cursor={{ fill: colors.grid, fillOpacity: 0.4 }} formatter={v => [fmt.value(v, format || 'decimal'), name || 'Value']} />
        <Bar dataKey="value" onClick={pick} cursor={onSelect ? 'pointer' : 'default'} isAnimationActive={false}>
          {rows.map((r, i) => (
            <Cell key={String(r.label) + '-' + i} fill={colors.series[0]} fillOpacity={selected && selected !== r.label ? 0.35 : 1} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function LineBlock({ rows, format, name }) {
  const colors = useChartColors();
  const fmt = useFormat();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
        <XAxis dataKey="label" tickFormatter={v => truncate(v, 14)} tick={tickProps(colors)} stroke={colors.grid} interval="preserveStartEnd" minTickGap={16} />
        <YAxis tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        <Tooltip contentStyle={tipStyle(colors)} formatter={v => [fmt.value(v, format || 'decimal'), name || 'Value']} />
        <Line type="monotone" dataKey="value" stroke={colors.series[0]} strokeWidth={2} dot={rows.length <= 60} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function ScatterBlock({ chart }) {
  const colors = useChartColors();
  const fmt = useFormat();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
        <XAxis type="number" dataKey="x" name={chart.xLabel || 'x'} tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        <YAxis type="number" dataKey="y" name={chart.yLabel || 'y'} tickFormatter={fmt.compact} tick={tickProps(colors)} stroke={colors.grid} />
        <Tooltip contentStyle={tipStyle(colors)} cursor={{ strokeDasharray: '3 3' }} />
        <Scatter data={chart.rows} fill={colors.series[0]} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function PieBlock({ chart }) {
  const colors = useChartColors();
  const fmt = useFormat();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={chart.rows} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={chart.type === 'doughnut' ? 60 : 0} outerRadius={100} isAnimationActive={false}>
          {chart.rows.map((r, i) => (
            <Cell key={r.label + '-' + i} fill={colors.series[i % colors.series.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={tipStyle(colors)} formatter={v => fmt.value(v, 'decimal')} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

function HeatBlock({ chart }) {
  const fmt = useFormat();
  const rowKeys = [...new Set(chart.rows.map(r => r.row))];
  const colKeys = [...new Set(chart.rows.map(r => r.col))];
  const lookup = new Map(chart.rows.map(r => [r.row + '\u0000' + r.col, r.value]));
  const values = chart.rows.map(r => r.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const intensity = v => (hi === lo ? 50 : 10 + ((v - lo) / (hi - lo)) * 80);
  return (
    <div className="heat-wrap">
      <div className="heat" style={{ gridTemplateColumns: 'auto repeat(' + colKeys.length + ', minmax(2.5rem, 1fr))' }}>
        <span />
        {colKeys.map(c => <span className="heat-head" key={'c-' + c}>{truncate(c, 10)}</span>)}
        {rowKeys.map(r => (
          <div className="heat-row" key={'r-' + r}>
            <span className="heat-head">{truncate(r, 14)}</span>
            {colKeys.map(c => {
              const v = lookup.get(r + '\u0000' + c);
              return (
                <span
                  className="heat-cell"
                  key={r + '|' + c}
                  title={r + ' / ' + c + ': ' + (v === undefined ? '-' : fmt.value(v, 'decimal'))}
                  style={{ background: v === undefined ? 'transparent' : 'color-mix(in srgb, var(--color-accent) ' + intensity(v) + '%, transparent)' }}
                />
              );
            })}
          </div>
        ))}
      </div>
      <table className="sr-only">
        <caption>{chart.title}</caption>
        <thead><tr><th scope="col">Row</th><th scope="col">Column</th><th scope="col">Value</th></tr></thead>
        <tbody>
          {chart.rows.map(r => (
            <tr key={r.row + '|' + r.col}><td>{r.row}</td><td>{r.col}</td><td>{fmt.value(r.value, 'decimal')}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartBody({ chart, rows }) {
  switch (chart.type) {
    case 'line': return <LineBlock rows={rows} name={chart.yLabel} />;
    case 'histogram': return <BarBlock rows={rows} histogram name={chart.yLabel} />;
    case 'scatter': return <ScatterBlock chart={chart} />;
    case 'heatmap': return <HeatBlock chart={chart} />;
    case 'pie':
    case 'doughnut': return <PieBlock chart={chart} />;
    default: return <BarBlock rows={rows} name={chart.yLabel} />;
  }
}

export function ChartPanel({ chart }) {
  let rows = chart.rows;
  let note = '';
  if (chart.type === 'bar' && rows.length > 40) {
    rows = [...rows].sort((a, b) => b.value - a.value).slice(0, 40);
    note = 'Showing the top 40 of ' + chart.rows.length + ' categories.';
  }
  const axes = chart.xLabel || chart.yLabel ? [chart.yLabel, chart.xLabel].filter(Boolean).join(' by ') : '';
  return (
    <section className="card chart-card">
      <h3>{chart.title}</h3>
      {chart.question ? <p className="muted">{chart.question}</p> : null}
      <div className={chart.type === 'heatmap' ? 'chart-box chart-scroll' : 'chart-box'}>
        <ChartBody chart={chart} rows={rows} />
      </div>
      {axes ? <p className="muted small">{axes}</p> : null}
      {note ? <p className="muted small">{note}</p> : null}
    </section>
  );
}
