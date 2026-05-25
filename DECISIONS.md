# Architectural Decisions & Assumptions (`DECISIONS.md`)

This document details the critical design choices, format selections, and boundaries handled in the prototype.

---

## 1. Selected Ingestion Formats & Justification

### A. SAP Procurement (Scope 1)
*   **Format**: Flat CSV export representing a customized SAP purchasing document log (e.g., matching structures of transaction `ME2N` or `ZFI_EMISSIONS` reports).
*   **Justification**: While SAP supports XML IDocs or BAPIs, sustainability leads typically work with offline CSV exports of procurement databases.
*   **Subset Handled**: We process plant codes (`WERKS`), posting date (`BUDAT`), quantity (`MENGE`), unit of measure (`MEINS`), cost (`DMBTR`), currency (`WAERS`), and material description (`MAKTX`). Unrecognized plant codes or unmapped materials are flagged.
*   **Subset Ignored**: Multi-currency conversions are simplified (defaulting to currency units as reported since carbon coefficients scale with activity volumes, not spend).

### B. Utility Electricity (Scope 2)
*   **Format**: Facilities portal CSV export including billing start/end dates, meter readings, multipliers, and calculated consumption.
*   **Justification**: Utility invoices are received monthly. Facility systems typically log these into flat sheets with invoice dates that do not align with calendar months.
*   **Prorating Decision**: Since billing periods often cross calendar boundaries (e.g., April 15 to May 14), we pro-rate consumption by days. If a bill spans multiple calendar months, we split it into separate normalized monthly sub-records so analysts see the correct monthly carbon distribution.

### C. Corporate Travel (Scope 3)
*   **Format**: Simulated HTTP API Pull returning a JSON batch (e.g. Concur Expense and Travel API).
*   **Justification**: Modern travel portals expose REST APIs that return travel itineraries. This shows our system's capacity to handle both file uploads and third-party integrations.
*   **Calculation Decision**: Rather than requiring distance fields, we calculate distances dynamically between airport codes (origin/destination) using the **Haversine formula**. We assign flight categories (Short-haul < 1600 km vs Long-haul >= 1600 km) and apply cabin-class multipliers (Economy vs Business) sourced from DEFRA databases.

---

## 2. Unresolved Ambiguities & PM Clarifications

Here is what we would ask the Product Manager if we were developing this in production:
1.  **Re-ingestion Policy**: If a file is uploaded twice, should we overwrite existing raw records or generate duplicates? (For the prototype, we treat each upload as a new batch, letting analysts reject duplicates manually).
2.  **Spend-Based Calculations**: Should we calculate carbon using spend multipliers when activity values (e.g. liters/kWh) are missing? (For the prototype, we require activity values and flag records with missing volumes).
3.  **Outlier Baselines**: How should we set outlier thresholds? (Currently, we flag consumption if it exceeds 3x the average of previously approved records for the facility).
