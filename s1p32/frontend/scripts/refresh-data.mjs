import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(here, '..');
const source = path.resolve(frontendRoot, '..', 'backend', 'output');
const target = path.resolve(frontendRoot, 'public', 'data');
const norm = p => p.split(path.sep).join('/');

function countFiles(dir) {
  let n = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    n += entry.isDirectory() ? countFiles(path.join(dir, entry.name)) : 1;
  }
  return n;
}

function stamp(dir) {
  try {
    const c = JSON.parse(fs.readFileSync(path.join(dir, 'frontend_contract.json'), 'utf8').replace(/^\uFEFF/, ''));
    return c.generated_at || 'unknown';
  } catch {
    return 'unknown';
  }
}

if (fs.existsSync(source)) {
  if (!norm(target).endsWith('frontend/public/data')) {
    console.error('Refusing to replace an unexpected folder: ' + target);
    process.exit(1);
  }
  fs.rmSync(target, { recursive: true, force: true });
  fs.cpSync(source, target, { recursive: true });
  console.log('Data refreshed: ' + countFiles(target) + ' files, generated ' + stamp(target));
} else if (fs.existsSync(path.join(target, 'frontend_contract.json'))) {
  console.log('Using the existing data copy (generated ' + stamp(target) + ')');
} else {
  console.error('No data found.');
  console.error('Run main.py and then export_for_frontend.py in the backend folder, then try again.');
  process.exit(1);
}
