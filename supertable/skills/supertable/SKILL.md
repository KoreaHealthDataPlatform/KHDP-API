---
name: supertable
description: Query SNUH SuperTable — a SQL gateway over FHIR and OMOP CDM clinical-research data. Use when the user asks about cohorts, patient counts, lab values, vitals, drug exposures, surgeries, or any analysis that needs SNUH's clinical database. Triggers on dataset names (`fhir`, `cdm`), table names (`patient`, `measurement`, `condition_occurrence`, `drug_exposure`, `operations`, `surgery_schedule`), and OMOP/FHIR vocabulary (HMAC patient IDs, ASA score, ICD-10, measurement_source_value). Also triggers on Korean clinical phrasing like "환자 수", "수술 통계", "혈압 분포", "검사 결과", or any prompt that involves the `khdp.supertable` Python module or the `supertable_*` MCP tools.
---

# SuperTable — operator's guide for Claude

SuperTable exposes two datasets through a single SQL endpoint:

- **`fhir`** — anonymized real FHIR resources from one day (100 patients).
  IDs are HMAC pseudonyms; event timestamps are jittered ±30 days per
  patient (so calendar dates are unreliable, but per-patient ordering
  and time-of-day are preserved).
- **`cdm`** — synthetic SNUH INSPIRE OMOP CDM (199 K patients, 2019–2030).
  Standard OMOP tables plus `cdm.operations` with INSPIRE-specific
  surgical fields (`asa`, `emop`, `antype`, OR in/out times).

**`fhir.*` and `cdm.*` do not join** — different ID systems.

## Operating procedure

1. **Prime context once** with `supertable_info` (no arguments). The
   result includes every dataset, every table, every column, the
   `requires_date_filter` flag, the `date_filter_columns`, and the full
   `policy_summary`. Cache it; only refetch if the user reports a
   schema change.

2. **Before writing SQL against any table**, decide whether you need
   `supertable_stat` for that table. The stats endpoint tells you the
   actual date range, row count, and which columns are mostly NULL —
   useful for narrowing date predicates and avoiding wasted joins.
   First call on a huge table can take 15–30 s; thereafter cached 1 h.

3. **For shape preview** (what do the values look like?), use
   `supertable_head` with `limit ≤ 100`. The server crafts the SQL,
   so this works on huge tables even without a date filter.

4. **Run queries with `supertable_query`.** Rows come back as objects
   keyed by column name. If `len(rows) == limit` the result was likely
   truncated — either raise the limit (max 50 000) or rewrite the SQL
   with `GROUP BY` / aggregation.

## Hard rules — the policy gate

These are enforced server-side. Don't try to bypass; just write
compliant SQL:

- Only `SELECT`, `WITH`, or `EXPLAIN SELECT`. **No** DDL, DML, COPY,
  ATTACH, LOAD, PRAGMA, transactions, USE, CALL.
- **No file or extension functions** — `read_parquet`, `read_csv`,
  `glob`, `load_extension`, …
- Tables outside the catalog are rejected. Stick to the
  `dataset.table` names from `supertable_info`.
- **Huge tables require a date filter** on one of their
  `date_filter_columns`:
  - `cdm.measurement`        → `_date_partition` or `measurement_date`
  - `cdm.condition_occurrence` → `_date_partition` or `condition_start_date`
  - `cdm.drug_exposure`      → `_date_partition` or `drug_exposure_start_date`
  - `fhir.observation`       → `date` or `effective_datetime`
- `LIMIT` is injected if omitted (default 100, max 50 000). Higher →
  HTTP 400. Don't try `limit: 1000000`.

## Heuristics

- **"How many patients have X?"** → `COUNT(DISTINCT person_id)` on the
  relevant `condition_occurrence` / `drug_exposure` filter, scoped by a
  date partition.
- **"What's the time series of Y?"** → `GROUP BY measurement_date`,
  truncated to month if the range is wide.
- **"What does table T contain?"** → start with `supertable_head` for a
  feel, then `supertable_stat` for ranges and NULL rates.
- **"Cohort summary"** → join `cdm.person`, optionally `cdm.death`, and
  any condition/drug tables with explicit date ranges. Always
  `WHERE _date_partition >= DATE 'YYYY-MM-DD'` to enable pruning.

## Korean conventions

`measurement_source_value` values follow SNUH conventions: `nibp_sbp`,
`nibp_dbp`, `hr`, `spo2`, `bt`, `rr` (vitals); `glu`, `creatinine`,
`hb`, `wbc`, `plt` (chem/cbc); `pao2`, `paco2`, `lactate` (gas); …

`cdm.operations.antype` is the anesthesia type abbreviation
(`G` = general, `S` = spinal, `M` = MAC, …). `asa` is the ASA-PS class.
`emop = 1` flags emergency operations.

## Don't

- Don't reveal patient identifiers in the response, even though they're
  HMAC-pseudonymized. They are still considered linkable if combined
  with the salt.
- Don't claim a calendar date in the `fhir` dataset is real — they're
  jittered ±30 days per patient.
- Don't expose the gateway URL or token to the user; they're in the
  agent's environment, not the user's.

## Failure modes you'll see

| State / exception in result | What it means |
|---|---|
| `state: "failed"` | DuckDB rejected the SQL (e.g. column not found). Fix and retry. |
| `state: "timeout"` | Query exceeded the statement timeout. Add `WHERE`/`GROUP BY` or raise `timeout_ms`. |
| `PolicyRejected` | One of the hard rules above. Read `.errors`. |
| `NotFound` | Unknown dataset/table. Recheck against `supertable_info`. |
| Over-limit error | You sent `limit > 50000`. Reduce, or aggregate. |
