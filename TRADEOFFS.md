# Project Tradeoffs (`TRADEOFFS.md`)

To build a high-quality prototype within the 4-day timeline, we prioritized data model integrity and normalizer mechanics over auxiliary infrastructure.

Here are the three features we deliberately did not build:

---

## 1. Document OCR Parsing for PDF Utility Bills
*   **Alternative**: Facilities teams often get PDF bills. An ideal app would let users drag-and-drop a PDF and use OCR (Tesseract, Document AI, or LLM vision) to pull dates and readings.
*   **Tradeoff Decision**: PDF OCR is highly fragile and requires third-party API keys or heavy Python models, which complicates local setup. Instead, we assumed the facilities portal lets users download a flat CSV report of meter logs, and built a parser that validates meter subtraction logic.

## 2. Dynamic Live Currency Exchange Rates
*   **Alternative**: Invoices contain various currencies (USD, EUR, INR, GBP). A production app would hit an external API (like Open Exchange Rates) to translate cost metadata into a single reporting currency (e.g. USD) based on the transaction date.
*   **Tradeoff Decision**: Since ESG reporting and audits are carbon-volume driven (measured in liters, kWh, or kilometers) rather than cost driven, cost is treated as non-calculational metadata. We store currencies as reported and avoided external API rate-limiting delays.

## 3. Production OAuth2.0 Single Sign-On (SSO)
*   **Alternative**: Enterprise applications require secure login, role permission groups, Active Directory integration, and token expirations.
*   **Tradeoff Decision**: Setting up full user auth blocks evaluator testing. We seeded three default mock users (`admin`, `analyst`, `auditor`) and built a visible Role Toggle in the sidebar. This allows the evaluator to switch roles instantly and check analyst controls vs auditor signing locks without logging in and out.
