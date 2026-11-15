import { useMemo } from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { useChartColors } from '../../hooks/useChartColors.js';
import { DataState } from '../shared/DataState.jsx';
import { SkeletonCard } from '../shared/SkeletonCard.jsx';
import { formatKind } from '../../utils/formatters.js';
import { truncate } from '../../utils/text.js';

export function Forecaster() {
  const query = useDataset('forecast');
  if (query.loading || query.error) {
    return <DataState query={query} label="forecast" skeleton={<SkeletonCard count={2} height={320} />} />;
  }
  return <ForecastBody f={query.data} />;
}

function ForecastBody({ f }) {
  const fmt = useFormat();
  const colors = useChartColors();
  const kind = formatKind(f.unit);
  const rows = useMemo(() => {
    const hist = f.history.map(r => ({ t: r.t, history: r.value }));
    const fut = f.forecast.map(r => ({
      t: r.t, forecast: r.value, low: r.low, band: r.low !== null && r.high !== null ? r.high - r.low : null,
    }));
    return [...hist, ...fut];
  }, [f]);
  const hasBand = f.forecast.some(r => r.low !== null && r.high !== null);
  const tip = { background: colors.surface, border: '1px solid ' + colors.grid, color: colors.textPrimary, borderRadius: '0.5rem' };
  const tick = { fill: colors.text, fontSize: 12 };
  return (
    <div className="stack">
      <section className="card chart-card">
        <h3>{f.metric ? 'Forecast: ' + f.metric : 'Forecast'}</h3>
        <p className="muted">{[f.horizon ? 'Horizon: ' + f.horizon : '', f.method ? 'Method: ' + f.method : ''].filter(Boolean).join('. ')}</p>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
              <XAxis dataKey="t" tickFormatter={v => truncate(v, 12)} tick={tick} stroke={colors.grid} interval="preserveStartEnd" minTickGap={16} />
              <YAxis tickFormatter={fmt.compact} tick={tick} stroke={colors.grid} />
              <Tooltip contentStyle={tip} formatter={v => fmt.value(v, kind)} />
              <Legend />
              {hasBand ? <Area type="monotone" dataKey="low" stackId="band" stroke="none" fill="transparent" legendType="none" tooltipType="none" isAnimationActive={false} connectNulls={false} /> : null}
              {hasBand ? <Area type="monotone" dataKey="band" stackId="band" stroke="none" fill={colors.series[0]} fillOpacity={0.18} legendType="none" tooltipType="none" isAnimationActive={false} connectNulls={false} /> : null}
              <Line type="monotone" dataKey="history" name="History" stroke={colors.series[0]} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="forecast" name="Forecast" stroke={colors.series[1]} strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="muted small">This is a forecast, not a guarantee.</p>
        <p><a href="#/monitor/predict">Try your own numbers on the Predict page</a></p>
      </section>
      <div className="grid">
        {f.error ? (
          <article className="card kpi">
            <p className="kpi-label">How far off it was on recent history</p>
            <p className="kpi-value">{f.error.mape !== null ? fmt.value(f.error.mape, 'percent') : (f.error.mae !== null ? fmt.value(f.error.mae, kind) : '-')}</p>
            <p className="muted small">
              {[
                f.error.mae !== null ? 'Average miss: ' + fmt.value(f.error.mae, kind) : '',
                f.error.baselineMae !== null ? 'Simple baseline miss: ' + fmt.value(f.error.baselineMae, kind) : '',
                f.error.period ? 'Tested on ' + f.error.period : '',
              ].filter(Boolean).join('. ')}
            </p>
          </article>
        ) : null}
        {f.note ? <article className="card"><p>{f.note}</p></article> : null}
      </div>
    </div>
  );
}
