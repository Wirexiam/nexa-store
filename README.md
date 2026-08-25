# Nexa Store

React storefront, private CRM, and customer order forms for digital subscription payments.

## Architecture

```
nexa-store/
  backend/                 FastAPI API (source of truth)
    app/
      catalog.py           Service catalog, prices, form rules
      models.py            SQLAlchemy Order (CRM fields only)
      sensitive.py         Temporary token handling; never persisted
      routers/admin.py     Private CRM endpoints
      routers/orders.py    Customer order page endpoints
  frontend/                React + Vite SPA
    src/pages/             catalog, /admin CRM, and /order/:id checkout
```

- **API-based:** React talks to `/api`. Vite proxies to FastAPI in development.
- **Catalog-driven:** the API is the source of truth for services, tariffs, periods, prices, and conditional token requirements. The React UI maps stable service keys to bundled SVG logos and service-specific field copy.
- **Database:** SQLite by default via `DATABASE_URL`. Switch the URL to PostgreSQL (`postgresql+psycopg://...`) without changing models.
- **Secrets policy:** access tokens, session tokens, passwords, and cookies are not columns on `Order`. A customer token is read only during `POST /api/orders/{id}/submit`, used to set `credentials_received` (boolean), then discarded. It is never logged or written to SQLite.

### Data stored per order

`id`, `customer_email`, `service`, `service_key`, `subscription_level`, `payment_period`, `amount`, `currency`, `status`, `credentials_received`, `created_at`, `updated_at`, `submitted_at`

Statuses: `В работе`, `Оплачено`, `Отменено`, `Ошибка`

## Setup

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --app-dir .
```

API: http://127.0.0.1:8000  
Docs: http://127.0.0.1:8000/docs  

Default admin key (from `.env`): `nexa-dev-admin`  
Send it as header `X-Admin-Key`. It is not stored in the database.

On first start the API creates `backend/data/nexa_store.db` and seeds demo orders.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173

- Storefront and service catalog: `/`
- Admin CRM: `/admin`, `/admin/orders`, `/admin/orders/{id}`
- Customer form: `/order/{id}`

For a separately hosted API, set `VITE_API_BASE_URL` before building the frontend. Leave it empty for the Vite proxy or when FastAPI serves `frontend/dist`.

### Local verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

cd ..\frontend
npm.cmd run build
```

Build the frontend before starting FastAPI for a production-style run. FastAPI serves the generated SPA and falls back to `index.html` for direct `/admin/...` and `/order/...` browser loads.

### PostgreSQL

Install `psycopg` (or `psycopg2`) and set:

```
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/nexa_store
```

Models already use portable SQLAlchemy types.

## Typical flow

1. Admin creates an order (or uses a seeded one) and copies `/order/{id}`.
2. Customer opens the link, confirms plan, enters email (and an access token only if the service requires it).
3. Submit updates CRM fields, drops the token from memory, and redirects to confirmation.
4. Admin filters orders and changes status from the table or the detail page.
