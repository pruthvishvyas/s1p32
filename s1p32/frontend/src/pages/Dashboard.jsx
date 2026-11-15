import { PageSection } from '../components/shared/PageSection.jsx';
import { ErrorBoundary } from '../components/shared/ErrorBoundary.jsx';
import { KPICards } from '../components/understand/KPICards.jsx';
import { ChartGrid } from '../components/understand/ChartGrid.jsx';
import { SegmentExplorer } from '../components/understand/SegmentExplorer.jsx';
import { AnomalyTable } from '../components/understand/AnomalyTable.jsx';
import { InsightCards } from '../components/decide/InsightCards.jsx';
import { RecommendationEngine } from '../components/decide/RecommendationEngine.jsx';
import { WhatIfSimulator } from '../components/decide/WhatIfSimulator.jsx';
import { GoalTracker } from '../components/decide/GoalTracker.jsx';
import { Forecaster } from '../components/monitor/Forecaster.jsx';
import { Predictor } from '../components/monitor/Predictor.jsx';
import { GoalProgress } from '../components/monitor/GoalProgress.jsx';
import { AlertCenter } from '../components/monitor/AlertCenter.jsx';
import { InteractiveExplorer } from '../components/explorer/InteractiveExplorer.jsx';
import { UserManual } from '../components/manual/UserManual.jsx';
import { DataHealth } from '../components/health/DataHealth.jsx';

export const DEFAULT_PAGE = 'understand/overview';

const PAGES = {
  'understand/overview': { title: 'Overview', intro: 'Key numbers and the charts that explain them.', render: () => (<><KPICards /><ChartGrid /></>) },
  'understand/segments': { title: 'Segments', intro: 'Groups of similar records.', render: () => <SegmentExplorer /> },
  'understand/anomalies': { title: 'Anomalies', intro: 'Unusual records worth a second look.', render: () => <AnomalyTable /> },
  'decide/insights': { title: 'Insights', intro: 'What the data says and what to do about it.', render: () => <InsightCards /> },
  'decide/recommendations': { title: 'Recommendations', intro: 'Actions in order of priority.', render: () => <RecommendationEngine /> },
  'decide/what-if': { title: 'What-if', intro: 'See how a change could play out.', render: () => <WhatIfSimulator /> },
  'decide/goals': { title: 'Goals', intro: 'Targets and how you are doing against them.', render: () => <GoalTracker /> },
  'monitor/forecast': { title: 'Forecast', intro: 'An estimate of what comes next.', render: () => <Forecaster /> },
  'monitor/predict': { title: 'Predict', intro: 'Enter details and get an estimate before it happens.', render: () => <Predictor /> },
  'monitor/progress': { title: 'Progress', intro: 'Latest values against targets.', render: () => <GoalProgress /> },
  'monitor/alerts': { title: 'Alerts', intro: 'Things that need attention now.', render: () => <AlertCenter /> },
  explore: { title: 'Explore', intro: 'Slice the numbers your own way.', render: () => <InteractiveExplorer /> },
  guide: { title: 'Guide', intro: 'A plain-English manual for this dashboard.', render: () => <UserManual /> },
  health: { title: 'Data health', intro: 'When the data was last updated and what is available.', render: () => <DataHealth /> },
};

export const PAGE_IDS = Object.keys(PAGES);

export function Dashboard({ route }) {
  const page = PAGES[route] || PAGES[DEFAULT_PAGE];
  return (
    <PageSection title={page.title} intro={page.intro}>
      <ErrorBoundary key={route} label={page.title}>
        {page.render()}
      </ErrorBoundary>
    </PageSection>
  );
}
