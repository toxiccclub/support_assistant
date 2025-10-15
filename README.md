# Support Assistant

Frontend: `frontend/` (index.html + app.js)
Backend: `backend/` (FastAPI)

Запуск backend:
- python -m venv venv
- \venv\Scripts\Activate.ps1
- pip install -r backend/requirements.txt
- uvicorn app.main:app --reload --port 8000

Frontend: 
- открыть `frontend/index.html` в браузере.
ИЛИ
- в другой от бека консоли
- python3 -m http.server 3000 --directory frontend