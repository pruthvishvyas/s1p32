import { useContract } from '../../hooks/useContract.js';
import { useDataset } from '../../hooks/useDataset.js';
import { useFormat } from '../../context/FormatContext.jsx';
import { ThemeToggle } from './ThemeToggle.jsx';

export function Header() {
  const contract = useContract();
  const summary = useDataset('summary');
  const fmt = useFormat();
  const name = contract.data ? contract.data.project.name : 'Dashboard';
  const when = summary.data && summary.data.lastRun ? summary.data.lastRun : (contract.data ? contract.data.generatedAt : '');
  return (
    <header className="topbar">
      <div>
        <p className="topbar-name">{name}</p>
        {when ? <p className="muted small">{'Updated ' + fmt.ago(when)}</p> : null}
      </div>
      <ThemeToggle />
    </header>
  );
}
