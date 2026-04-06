# Finance Backend

A backend API for a finance dashboard system with role-based access control, financial record management, and summary analytics.

Built with **Python + Flask + SQLite**. No ORM — raw SQL for full transparency. Zero external dependencies beyond Flask itself.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Setup](#setup)
- [Default Credentials](#default-credentials)
- [API Reference](#api-reference)
  - [Auth](#auth)
  - [Users](#users)
  - [Records](#records)
  - [Dashboard](#dashboard)
- [Role Permissions](#role-permissions)
- [Data Models](#data-models)
- [Assumptions and Tradeoffs](#assumptions-and-tradeoffs)

---

## Tech Stack

| Layer        | Choice         | Reason                                                    |
|--------------|----------------|-----------------------------------------------------------|
| Language     | Python 3       | Readable, concise, widely understood                      |
| Framework    | Flask          | Lightweight; full control without magic                   |
| Database     | SQLite         | Zero config, file-based, plenty for this scope            |
| Auth         | JWT (HS256)    | Stateless; hand-rolled to avoid extra deps                |
| Passwords    | PBKDF2-SHA256  | Stdlib `hashlib` — secure without needing bcrypt          |

---

## Architecture

```
finance-backend/
├── app.py           # App factory, blueprint registration, error handlers
├── config.py        # JWT secret, expiry, role hierarchy
├── db.py            # SQLite connection, schema creation, seed data
├── auth_utils.py    # Password hashing (PBKDF2) and JWT encode/decode
├── middleware.py    # @require_auth and @require_role decorators
├── validators.py    # Input validation for every route (no third-party lib)
└── routes/
    ├── auth.py      # POST /auth/login
    ├── users.py     # User CRUD (admin-gated)
    ├── records.py   # Financial record CRUD with filtering + pagination
    └── dashboard.py # Summary, trends, categories, insights
```

### Request lifecycle

```
HTTP request
  → require_auth   (verify JWT, attach g.current_user)
  → require_role   (check role level against minimum)
  → validator      (validate and sanitize input)
  → route handler  (business logic + DB query)
  → JSON response
```

---

## Setup

**Requirements:** Python 3.8+ with Flask and PyJWT installed.

```bash
# 1. Clone the repo
git clone <repo-url>
cd finance-backend

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Set environment variables
export JWT_SECRET="your-secret-key-here"   # Default is a dev placeholder
export DATABASE_PATH="finance.db"           # Default

# 5. Run
python3 app.py
```

The server starts at `http://localhost:5000`. On first run, the database is created and seeded automatically.

---

## Default Credentials

Three users are seeded on first run:

| Username  | Password    | Role     |
|-----------|-------------|----------|
| `admin`   | `admin123`  | admin    |
| `analyst` | `analyst123`| analyst  |
| `viewer`  | `viewer123` | viewer   |

**Change these before any real deployment.**

---

## API Reference

All protected routes require:
```
Authorization: Bearer <token>
```

All request bodies use `Content-Type: application/json`.

---

### Auth

#### `POST /auth/login`

Authenticate and receive a JWT token.

**Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response `200`:**
```json
{
  "token": "eyJ...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

**Errors:** `401` invalid credentials, `403` inactive account, `422` validation failure.

---

### Users

All user management endpoints require the `admin` role, except `GET /users/<id>` which allows a user to fetch their own profile.

#### `GET /users/`
List all users. Optional query param: `?status=active|inactive`

#### `POST /users/`
Create a new user.

**Request:**
```json
{
  "username": "jane",
  "email": "jane@example.com",
  "password": "securepass",
  "role": "analyst"
}
```

**Response `201`:** Created user object (password excluded).

#### `GET /users/<id>`
Fetch a single user. Admins can fetch any user; others can only fetch themselves.

#### `PATCH /users/<id>`
Partially update a user. All fields optional.

```json
{
  "role": "analyst",
  "status": "inactive",
  "email": "newemail@example.com"
}
```

#### `DELETE /users/<id>`
Permanently delete a user. Admins cannot delete their own account.

---

### Records

#### `GET /records/`
List financial records with optional filtering and pagination.

**Minimum role:** `viewer`

**Query parameters:**

| Param       | Type   | Description                        |
|-------------|--------|------------------------------------|
| `type`      | string | `income` or `expense`              |
| `category`  | string | Partial match                      |
| `from_date` | date   | `YYYY-MM-DD` lower bound           |
| `to_date`   | date   | `YYYY-MM-DD` upper bound           |
| `page`      | int    | Page number (default: 1)           |
| `per_page`  | int    | Results per page (default: 20, max: 100) |

**Response `200`:**
```json
{
  "records": [ ... ],
  "pagination": {
    "total": 42,
    "page": 1,
    "per_page": 20,
    "pages": 3
  }
}
```

#### `GET /records/<id>`
Fetch a single record. **Minimum role:** `viewer`

#### `POST /records/`
Create a new financial record. **Minimum role:** `analyst`

**Request:**
```json
{
  "amount": 1500.00,
  "type": "income",
  "category": "Freelance",
  "date": "2025-04-01",
  "notes": "Website project"
}
```

**Response `201`:** Created record object.

#### `PATCH /records/<id>`
Partially update a record. All fields optional. **Minimum role:** `admin`

#### `DELETE /records/<id>`
Soft-delete a record (sets `deleted_at`, never truly removed). **Minimum role:** `admin`

---

### Dashboard

#### `GET /dashboard/summary`
Total income, expenses, net balance, and record count.

**Minimum role:** `viewer`

**Query params:** `from_date`, `to_date` (both optional, `YYYY-MM-DD`)

**Response:**
```json
{
  "summary": {
    "total_income": 18950.0,
    "total_expenses": 5330.0,
    "net_balance": 13620.0,
    "record_count": 12,
    "period": { "from": "2025-01-01", "to": "2025-03-31" }
  }
}
```

#### `GET /dashboard/categories`
Income and expenses grouped by category.

**Minimum role:** `viewer`

**Query params:** `?type=income|expense` (optional)

**Response:**
```json
{
  "categories": [
    { "category": "Salary", "type": "income", "total": 15000.0, "count": 3 },
    { "category": "Rent",   "type": "expense", "total": 3600.0,  "count": 3 }
  ]
}
```

#### `GET /dashboard/recent`
Most recent records.

**Minimum role:** `viewer`

**Query params:** `?limit=10` (default: 10, max: 50)

#### `GET /dashboard/trends`
Monthly income and expense totals.

**Minimum role:** `analyst`

**Query params:** `?months=12` (default: 12, max: 60)

**Response:**
```json
{
  "trends": [
    { "month": "2025-01", "income": 5000.0, "expenses": 1280.0, "net": 3720.0 },
    { "month": "2025-02", "income": 8200.0, "expenses": 2100.0, "net": 6100.0 }
  ],
  "months": 12
}
```

#### `GET /dashboard/insights`
Savings rate and top-5 spending categories / income sources.

**Minimum role:** `analyst`

**Response:**
```json
{
  "insights": {
    "savings_rate_pct": 71.9,
    "top_expense_categories": [
      { "category": "Rent", "total": 3600.0 }
    ],
    "top_income_sources": [
      { "category": "Salary", "total": 15000.0 }
    ]
  }
}
```

---

## Role Permissions

| Action                          | Viewer | Analyst | Admin |
|---------------------------------|--------|---------|-------|
| Login                           | ✓      | ✓       | ✓     |
| View own profile                | ✓      | ✓       | ✓     |
| List / view records             | ✓      | ✓       | ✓     |
| Dashboard summary               | ✓      | ✓       | ✓     |
| Dashboard categories            | ✓      | ✓       | ✓     |
| Dashboard recent activity       | ✓      | ✓       | ✓     |
| Dashboard trends                |        | ✓       | ✓     |
| Dashboard insights              |        | ✓       | ✓     |
| Create records                  |        | ✓       | ✓     |
| Update / delete records         |        |         | ✓     |
| Manage users (CRUD)             |        |         | ✓     |

---

## Data Models

### users

| Column       | Type    | Notes                                 |
|--------------|---------|---------------------------------------|
| `id`         | INTEGER | Primary key                           |
| `username`   | TEXT    | Unique, min 3 chars                   |
| `email`      | TEXT    | Unique, validated format              |
| `password`   | TEXT    | PBKDF2-SHA256 hash                    |
| `role`       | TEXT    | `viewer` / `analyst` / `admin`        |
| `status`     | TEXT    | `active` / `inactive`                 |
| `created_at` | TEXT    | ISO datetime (UTC)                    |
| `updated_at` | TEXT    | ISO datetime (UTC)                    |

### financial_records

| Column       | Type    | Notes                                 |
|--------------|---------|---------------------------------------|
| `id`         | INTEGER | Primary key                           |
| `amount`     | REAL    | Must be positive                      |
| `type`       | TEXT    | `income` / `expense`                  |
| `category`   | TEXT    | Free text                             |
| `date`       | TEXT    | `YYYY-MM-DD`                          |
| `notes`      | TEXT    | Optional                              |
| `created_by` | INTEGER | Foreign key → `users.id`              |
| `created_at` | TEXT    | ISO datetime (UTC)                    |
| `updated_at` | TEXT    | ISO datetime (UTC)                    |
| `deleted_at` | TEXT    | NULL = active, set = soft-deleted     |

---

## Assumptions and Tradeoffs

**JWT is hand-rolled.**
The JWT implementation uses Python's stdlib `hmac` and `hashlib` to avoid any third-party dependency. It is HS256-compliant in behavior. In production, replace with PyJWT for broader compliance and edge-case handling.

**SQLite over PostgreSQL.**
SQLite is the right default for a focused assessment. The raw SQL queries would work on PostgreSQL with minimal changes (only `datetime('now')` → `NOW()` and `strftime` → `date_trunc`).

**Soft deletes on records, hard deletes on users.**
Financial records are soft-deleted so audit history is preserved. Users can be hard-deleted since their records retain the `created_by` FK (the join in list queries will fail gracefully if the user is gone — this could be addressed with a `LEFT JOIN` in a production version).

**Analyst can create but not modify records.**
The assignment left role boundaries open. I chose to let analysts create records (since they're working with data daily) but restrict edits and deletes to admins only, to maintain data integrity.

**No refresh tokens.**
Tokens expire after 24 hours. A production system would pair access tokens with refresh tokens and a token blacklist.

**Pagination defaults to 20 per page.**
Avoids returning unbounded result sets by default. Max is capped at 100.

**Category is a free-text field.**
Rather than a fixed enum or a separate `categories` table, category is stored as text and filtered with `LIKE`. This is simpler and flexible. A separate table would be cleaner for a larger system.
