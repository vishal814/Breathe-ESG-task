# Data Model Documentation (`MODEL.md`)

Our data schema is engineered to guarantee strict audit integrity, multi-tenant isolation, automated carbon calculations, and a comprehensive chronological change log.

---

## 1. Relational Database Schema Overview

We use SQLite for the prototype database, mapping the following core Django models:

```
+------------------+         +--------------------------+
|      Client      | <-----+ |     LocationMapping      | (Resolves Plant codes to Region / Grid factors)
+------------------+         +--------------------------+
  ^         ^    ^
  |         |    +---------+
  |         |              |
  |  +------+---------+    | +--------------------------+
  |  | IngestionSource| <--+-|        RawRecord         | (Immutable raw source data as JSON)
  |  +----------------+      +--------------------------+
  |                            ^
  |                            | (1-to-Many for calendar split pro-rating)
  |                          v
  |  +------------------------+      +------------------+
  +--|    NormalizedRecord    | <--- |    AuditTrail    | (Logs all overrides, approvals & locks)
     +------------------------+      +------------------+
```

---

## 2. Key Architecture Design Pillars

### A. Strict Multi-Tenancy
All operational tables (`IngestionSource`, `RawRecord`, `NormalizedRecord`, `LocationMapping`) maintain a foreign key referencing the `Client` table. 
- Custom queryset filtering is implemented at the API controller layer (`views.py`) to restrict records queries based on the `?client=ID` parameter.
- This secures isolation between corporate clients (e.g. Acme Corp vs Globex Industries).

### B. Scope 1/2/3 Categorization
We map incoming rows to standard Greenhouse Gas (GHG) Protocol scopes:
- **Scope 1 (Direct)**: SAP procurement fuel records (e.g., Diesel, Natural Gas, Heating Oil burned directly in generators or boilers).
- **Scope 2 (Indirect - Electricity)**: Utility energy invoices pro-rated and converted to emissions via grid-intensity lookup tables.
- **Scope 3 (Other Indirect)**: Travel flights, hotel room-nights, and local ground transport.

### C. Source-of-Truth Tracking & Lineage
To ensure that audit records can be traced back to original inputs:
1. Files or API payloads are saved in `IngestionSource` (stores the raw text/JSON).
2. Each line of the CSV or JSON array creates a `RawRecord` (stores raw key-values as a JSONField).
3. `NormalizedRecord` stores a foreign key `raw_record_id` representing its origin. Even when utility bills are split across months, they link back to the exact same raw invoice record, preserving the source lineage.

### D. Unit Normalization Engine
Varying units of measure (e.g., `LIT`, `L`, `LITER`, `KG`, `KILO`, `pkm`, `room-nights`) are parsed by the `normalization_engine.py` using lookup dictionary matchers. They are converted into standardized baselines:
- Fuels -> Liters (`L`), Kilograms (`KG`), or Cubic Meters (`M3`).
- Electricity -> Kilowatt-Hours (`kWh`).
- Travel -> Passenger-Kilometers (`pkm`) or room-nights.
Emissions are calculated as $ActivityValue \times EmissionFactor / 1000$ to output standard Metric Tonnes of CO2 equivalent ($tCO_2e$).

### E. Auditable Change Log (Audit Trail)
Every action taken on a normalized record (such as ingestion, approval, rejection, or data overrides) triggers a log insertion into the `AuditTrail` table.
- When an analyst overrides values (e.g. corrects an outlier), the API view computes the diff:
  ```json
  {
    "activity_value": {"old": 1500.0, "new": 150.0},
    "co2e_emissions_t": {"old": 4.02, "new": 0.402}
  }
  ```
- This change dictionary is stored inside the `changed_fields` JSONField along with the acting user's ID and their mandatory justification comment.
