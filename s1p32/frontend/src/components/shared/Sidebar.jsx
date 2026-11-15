import { useContract } from '../../hooks/useContract.js';
import { Icon } from './Icon.jsx';

export const NAV_GROUPS = [
  { title: 'Understand', items: [
    { id: 'understand/overview', label: 'Overview', icon: 'overview' },
    { id: 'understand/segments', label: 'Segments', icon: 'segments' },
    { id: 'understand/anomalies', label: 'Anomalies', icon: 'anomalies' },
  ] },
  { title: 'Decide', items: [
    { id: 'decide/insights', label: 'Insights', icon: 'insights' },
    { id: 'decide/recommendations', label: 'Recommendations', icon: 'recommendations' },
    { id: 'decide/what-if', label: 'What-if', icon: 'whatif' },
    { id: 'decide/goals', label: 'Goals', icon: 'goals' },
  ] },
  { title: 'Monitor', items: [
    { id: 'monitor/forecast', label: 'Forecast', icon: 'forecast' },
    { id: 'monitor/predict', label: 'Predict', icon: 'predict' },
    { id: 'monitor/progress', label: 'Progress', icon: 'progress' },
    { id: 'monitor/alerts', label: 'Alerts', icon: 'alerts' },
  ] },
  { title: 'More', items: [
    { id: 'explore', label: 'Explore', icon: 'explore' },
    { id: 'guide', label: 'Guide', icon: 'guide' },
    { id: 'health', label: 'Data health', icon: 'health' },
  ] },
];

export function Sidebar({ route }) {
  const contract = useContract();
  const name = contract.data ? contract.data.project.name : 'Dashboard';
  return (
    <nav className="sidebar" aria-label="Main">
      <p className="sidebar-brand">{name}</p>
      {NAV_GROUPS.map(group => (
        <div className="sidebar-group" key={group.title}>
          <p className="sidebar-title">{group.title}</p>
          <ul>
            {group.items.map(item => (
              <li key={item.id}>
                <a className={'sidebar-link' + (item.id === route ? ' active' : '')} href={'#/' + item.id} aria-current={item.id === route ? 'page' : undefined}>
                  <Icon name={item.icon} />
                  <span>{item.label}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
