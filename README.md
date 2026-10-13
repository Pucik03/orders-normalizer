# Orders Normalizer

A small FastAPI service that fetches `SOURCE_URL`, normalizes Russian phone numbers,
deduplicates by phone (maximum `amount`, then latest `created_at`) and returns the
required `clients` and `stats` JSON.

## Local run

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://127.0.0.1:8000/clients

## Deploy to Render

1. Create a GitHub repository and upload `app.py`, `requirements.txt`, and `render.yaml`.
2. In Render, choose **New + → Blueprint** and connect the repository.
3. Deploy the service. Render will provide a public URL.
4. Open `https://YOUR-SERVICE.onrender.com/clients` to get the required JSON.
5. Submit that exact `/clients` URL unless the task's checker specifies a different endpoint.

The service fetches the source on every request, so it doesn't accumulate duplicate records
between syncs and repeated requests reflect the same source data.
