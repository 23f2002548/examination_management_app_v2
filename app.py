"""Root entry point - delegates to backend/app.py"""
from backend.app import app

if __name__ == '__main__':
    print('Examination Management Portal: http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
