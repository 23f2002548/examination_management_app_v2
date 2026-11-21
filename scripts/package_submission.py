"""Create and validate a source ZIP with exactly one project folder at its root."""
from pathlib import Path
import zipfile
import hashlib

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output' / 'submission'
OUT.mkdir(parents=True, exist_ok=True)
TARGET = OUT / 'examination_management_23f2002548.zip'
FOLDER = 'examination_management_23f2002548'

top_files = ['app.py', 'worker.py', 'run.py', 'init_db.py', 'README.md', '.gitignore']
files = [ROOT / p for p in top_files if (ROOT / p).exists()]

# Backend source (excluding pycache, .pyc, db, secrets)
for p in (ROOT / 'backend').rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.db') and p.name != '.secret':
        files.append(p)

# Frontend source (excluding node_modules, dist)
for p in (ROOT / 'frontend').rglob('*'):
    if p.is_file() and 'node_modules' not in p.parts and 'dist' not in p.parts:
        files.append(p)

# Built frontend dist (required by Flask to serve)
dist = ROOT / 'frontend' / 'dist'
if not (dist / 'index.html').exists():
    raise SystemExit('Run: cd frontend && npm run build  before packaging')
for p in dist.rglob('*'):
    if p.is_file():
        files.append(p)

# Scripts
for p in (ROOT / 'scripts').rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:
        files.append(p)

with zipfile.ZipFile(TARGET, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in files:
        z.write(p, FOLDER + '/' + p.relative_to(ROOT).as_posix())
    z.writestr(FOLDER + '/instance/.gitkeep', '')

with zipfile.ZipFile(TARGET) as z:
    assert z.testzip() is None
    roots = {n.split('/')[0] for n in z.namelist()}
    assert roots == {FOLDER}, f'Unexpected root folders: {roots}'
    assert FOLDER + '/app.py' in z.namelist()
    assert FOLDER + '/backend/app.py' in z.namelist()
    assert FOLDER + '/backend/models.py' in z.namelist()

digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
(TARGET.with_suffix('.sha256')).write_text(digest + '  ' + TARGET.name + '\n')
print(f'{TARGET}\n{len(files)+1} files; SHA256 {digest}')
