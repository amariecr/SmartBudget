# SmartBudget — Flask group project starter

A classroom MVP for personal income/expense tracking, monthly category budgets, and manual savings goals.

## Setup (Windows PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY = 'replace-with-a-random-secret-for-local-use'
python app.py
```
Open http://127.0.0.1:5000. To run tests: `python -m pytest -q`.

## Docker
```powershell
docker build -t smartbudget .
docker run --rm -p 8000:8000 -e SECRET_KEY='replace-with-a-random-secret' smartbudget
```
Open http://localhost:8000. Docker SQLite data is not persistent unless you mount a volume.

## Deployment
On Render, create a Python web service, or deploy the Dockerfile. Set a strong `SECRET_KEY` and a `DATABASE_URL` for a provisioned PostgreSQL database. Avoid using ephemeral SQLite storage on Render: data may be lost after restart/redeploy. Never commit secrets or database files to GitHub.

## Notes
- Auth, add/delete transactions, category budgets, savings goals, and contributions are implemented.
- Editing transactions/goals, filtering transaction history separately, richer charts, and production-quality validation and security controls are future work.
- Monthly balance = recorded monthly income minus expenses, not a bank account balance.
- Savings contributions are manually tracked, not bank transfers and not subtracted from transactions automatically.
- The `db.create_all()` approach is appropriate for this educational starter but does not manage schema changes; use migrations for evolving deployments.
