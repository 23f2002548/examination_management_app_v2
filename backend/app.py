"""Main Flask application entry point."""
import sys
from pathlib import Path

# Ensure project root is in path so 'backend' package is resolvable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import create_app

app = create_app()

if __name__ == '__main__':
    print('Examination Management Portal running at http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
