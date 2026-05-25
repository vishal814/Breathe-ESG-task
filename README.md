# Breathe ESG | Ingestion, Normalization & Audit Ledger Platform

A Django and React prototype designed to ingest activity data from SAP, Utility, and Travel platforms, calculate Scope 1/2/3 carbon emissions, flag anomalies, and provide an analyst audit log.

---

## Deliverables & Architecture

Please review the following documentation files located in the project root:
- [MODEL.md](file:///d:/Breathe-ESG-task/MODEL.md) - Database schema, multi-tenancy, and audit logs logic.
- [DECISIONS.md](file:///d:/Breathe-ESG-task/DECISIONS.md) - Format selections, calendar pro-rating, and PM questions.
- [TRADEOFFS.md](file:///d:/Breathe-ESG-task/TRADEOFFS.md) - Omitted features (OCR, currencies, login auth) and justifications.
- [SOURCES.md](file:///d:/Breathe-ESG-task/SOURCES.md) - Real-world research, sample data structures, and production failure modes.

---

## Installation & Running Locally

Ensure you have **Python 3.13+** and **Node v24+** installed.

### Option A: Local Dev Setup (Recommended for hot-reloading)

#### 1. Setup Backend (Django REST)
Open a terminal in the root directory:
```powershell
# Create venv and activate (already completed by agent)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Navigate to backend directory
cd backend

# Install dependencies (already completed by agent)
pip install -r requirements.txt

# Run migrations (already completed by agent)
python manage.py migrate

# Seed databases with clients, grid intensities, airport coordinates, and carbon factors
python manage.py seed_data

# Start local server
python manage.py runserver 0.0.0.0:8000
```
The API server will run at: `http://localhost:8000/api/`

#### 2. Setup Frontend (React + Vite)
Open a new terminal in the root directory:
```powershell
# Navigate to frontend directory
cd frontend

# Install dependencies (already completed by agent)
npm install

# Start Vite dev server
npm run dev
```
The React interface will run at: `http://localhost:5173/`

---

### Option B: Running with Docker Compose
If you prefer running inside containers, execute this in the root directory:
```powershell
docker-compose up --build
```
- Backend runs at `http://localhost:8000/api/`
- Frontend runs at `http://localhost:5173/`

---

## Running Automated Test Suite
To verify the normalization algorithms, Haversine formula, calendar pro-rating splits, and validation anomaly flagging:
```powershell
cd backend
..\venv\Scripts\python.exe manage.py test
```

---

## Evaluator Workbench Walkthrough

Once both servers are running, navigate to `http://localhost:5173/` in your browser:

1.  **Select Workspace**: Switch between **Acme Corporation** and **Globex Industries** in the sidebar.
2.  **Role Switcher**:
    -   Toggle **Analyst**: Access upload forms, API pull triggers, overrides, and approval/rejections.
    -   Toggle **Auditor**: Simulates auditor inspection. All edit and action controls are blocked. Accesses the "Sign-off Period" lock features.
3.  **Data Ingestion Workbench**:
    -   Click the **Data Ingestion** tab.
    -   Download sample CSV files (`sap_procurement_export.csv` and `utility_portal_export.csv`) using the links provided.
    -   Upload the files using the drag-and-drop bars to see rows process in real-time.
    -   Click **Execute API Ingestion Pull** to see a simulated Concur Travel JSON API pull with step-by-step console logs.
4.  **Analyst Records Workbench**:
    -   Filter records by Scope (1/2/3), Category (Fuel, Electricity, Travel), or Status.
    -   Click any row to open the **Detail Drawer**.
    -   Observe the calculation breakdown recipe, side-by-side raw JSON comparisons, and the timeline audit log.
    -   Click **Override / Correct Data** to edit values. Enter a comment to see the changes log immediately onto the audit timeline.
    -   Select checkboxes to trigger bulk approval or bulk rejection.
5.  **Auditor Sign-off**:
    -   Switch role to **Auditor**.
    -   Click **Sign-off Period** in the sidebar. Select your dates and click lock.
    -   Approved records in that range will freeze, showing a locked lock icon.
