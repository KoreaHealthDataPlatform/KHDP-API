# SNUH SuperTable — Usage Guide

> **For AI agents & researchers.** Structured to be loaded once as LLM
> context. Read at session start; everything you need to query SuperTable
> from `khdp` is here.

---

## 1. What this is

A read-only HTTP/JSON SQL gateway over SNUH's clinical-research data.

- Two datasets are exposed: **`fhir`** (anonymized FHIR resources) and
  **`cdm`** (synthetic SNUH INSPIRE OMOP CDM).
- You write **SQL**, the gateway runs it on **DuckDB** against the
  underlying storage, and returns **JSON rows** (one object per row).
- A deterministic policy gate validates every query before execution.

You access the gateway through the `khdp` package:

```python
from khdp.supertable import Client
```

---

## 2. Configuration

Two env vars (or pass them directly to `Client(...)`):

| Variable | Default | Notes |
|---|---|---|
| `SUPERTABLE_BASE_URL` | — | required (e.g. `https://supertable.example.org`) |
| `SUPERTABLE_TOKEN`    | — | bearer token issued by the SuperTable team |

```python
import os
os.environ["SUPERTABLE_BASE_URL"] = "https://..."
os.environ["SUPERTABLE_TOKEN"] = "..."

from khdp.supertable import Client
with Client() as c:
    ...
```

---

## 3. Endpoints — one-line each

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/info[/{dataset}[/{table}]]` | **catalog** — load this first |
| GET | `/v1/stat[/{dataset}[/{table}]]` | **value stats** (row count, MIN/MAX, null count) |
| GET | `/v1/head/{dataset}/{table}?limit=N` | first N rows (max 100) for shape preview |
| POST | `/v1/query` | submit SQL — **stateless, synchronous** |

The Python client wraps these:

```python
c.info()                       # /v1/info
c.info("fhir")                 # /v1/info/fhir
c.info("fhir", "patient")      # /v1/info/fhir/patient
c.datasets()                   # convenience: ["cdm", "fhir"]
c.tables("cdm")                # convenience: list of CDM tables
c.columns("cdm", "person")     # convenience: column list

c.stat("cdm", "measurement")
c.stat("cdm", "measurement", refresh=True)

c.head("fhir", "patient", limit=10)

c.query("SELECT ...")          # list[dict]
c.df("SELECT ...")             # pandas DataFrame (needs `pip install khdp[pandas]`)
c.polars("SELECT ...")         # polars DataFrame (needs polars)
c.arrow("SELECT ...")          # pyarrow Table (needs pyarrow)
```

---

## 4. The two datasets in 30 seconds

### `fhir` — anonymized real FHIR data (1 day, 100 patients)

| Table | Rows | Date column(s) | Notes |
|---|---:|---|---|
| `patient` | 100 | — | `patient_id_anon`, `gender`, `year_of_birth_bin`. No names. |
| `observation` ⚠️ | 715K | `date`, `effective_datetime` | Lab + clinical + exam. **Date filter required.** |
| `diagnostic_report` | 4.5K | `date`, `effective_datetime` | imaging (IMG) + pathology (PAT). |
| `procedure` | 875 | `date`, `performed_start` | from per-patient bundles. |
| `composition` | 11K | `date`, `composition_datetime` | clinical / nursing notes with sections. |
| `surgery_schedule` | 283 | `surgery_date` | OR schedule. |

Anonymization in effect:
- IDs are HMAC pseudonyms — joins by `patient_id_anon` work across tables.
- Birth dates collapse to 5-yr bins (`"1955-1959"`, `"90+"`).
- Heights/weights collapse to 5-unit bins.
- All event timestamps are **jittered ±30 days per-patient deterministically**
  (time-of-day preserved). Calendar dates aren't reality; relative ordering
  within a patient is.
- Free-text fields (`surgery_name`, `diagnosis_name`, `section.text`, …)
  are regex-scrubbed for KR names, RRNs, phones, EMR IDs, dates.

### `cdm` — synthetic SNUH INSPIRE OMOP CDM (199K patients, 2019–2030)

| Table | Rows | Date column(s) | Notes |
|---|---:|---|---|
| `person` | 199K | — | demographics. `gender_concept_id` 8507=M / 8532=F. |
| `death` | 27K | `_date_partition`, `death_date` | |
| `visit_occurrence` | 261K | `_date_partition`, `visit_start_date` | inpatient surgical encounters. |
| `procedure_occurrence` | 261K | `_date_partition`, `procedure_date` | ICD-10-PCS. |
| `condition_occurrence` ⚠️ | 4.9M | `_date_partition`, `condition_start_date` | ICD-10. **Date filter required.** |
| `drug_exposure` ⚠️ | 21M | `_date_partition`, `drug_exposure_start_date` | **Date filter required.** |
| `measurement` ⚠️ | 259M | `_date_partition`, `measurement_date` | vitals + labs. **Date filter required.** |
| `observation_period` | 199K | `_date_partition`, `observation_period_start_date` | per-patient windows. |
| `operations` | 261K | `_date_partition`, `op_date` | INSPIRE extension: `asa`, `emop`, `antype`, `icd10_pcs`, OR-in/out times. |

`_date_partition` is monthly-truncated (`'2025-01-01'` means "Jan 2025").
Both `_date_partition` and the natural date column are valid filter
predicates — partition pruning handles either.

---

## 5. Query — stateless, synchronous

```python
rows = c.query(
    "SELECT gender, COUNT(*) AS n FROM cdm.person GROUP BY 1 ORDER BY n DESC"
)
# [{'gender_concept_id': 8507, 'n': 102134},
#  {'gender_concept_id': 8532, 'n':  97397}]
```

Rows are **objects keyed by column name** — no separate columns array.
`len(rows) == limit` means results may have been cut off; either raise
`limit` (max 50 000) or aggregate.

### Need more rows?

The API is stateless. Three options:

1. **Re-issue with a larger `limit`** (up to 50 000):
   ```python
   c.query("SELECT * FROM cdm.operations WHERE _date_partition >= DATE '2025-01-01'",
           limit=50000)
   ```
2. **Aggregate in SQL** — usually what you actually want:
   ```python
   c.query(
       "SELECT department, COUNT(*) FROM cdm.operations "
       "WHERE _date_partition >= DATE '2025-01-01' GROUP BY 1"
   )
   ```
3. **Keyset-chunk** in your own loop (LLM friendly):
   ```python
   last_id = 0
   while True:
       rows = c.query(
           "SELECT * FROM cdm.operations "
           f"WHERE op_id > {last_id} AND _date_partition >= DATE '2025-01-01' "
           "ORDER BY op_id LIMIT 50000"
       )
       if not rows: break
       process(rows)
       last_id = rows[-1]["op_id"]
   ```

### Cancellation

Drop the HTTP connection (or `Ctrl-C` your script). DuckDB interrupts
cooperatively at the next batch boundary.

---

## 6. Policy gate (read once, save tokens)

SQL is parsed (sqlglot) and checked **before** DuckDB sees it.
Violations raise `PolicyRejected`.

### Hard rules

1. **One statement only** — `SELECT`, `WITH …`, `EXPLAIN SELECT`.
2. **No DDL/DML/transactions/admin** — `INSERT`, `UPDATE`, `DELETE`,
   `CREATE`, `DROP`, `ALTER`, `COPY`, `ATTACH`, `LOAD`, `PRAGMA`,
   `SET`, `USE`, `CALL`, `BEGIN/COMMIT/ROLLBACK`.
3. **No file/path functions** — `read_parquet`, `read_csv`, `read_json`,
   `glob`, `load_extension`, …
4. **Allow-listed tables only** — see `info()["tables"]`.
5. **Huge tables require a date filter** — tables flagged ⚠️ above.
6. **Implicit LIMIT** — server injects `LIMIT 100` if omitted.
   Maximum 50 000; higher → HTTP 400.
7. **Statement timeout** — 60 s default. Pass `timeout_ms=` for longer.

### Examples

```sql
-- ✅ OK
SELECT gender, COUNT(*) FROM cdm.person GROUP BY 1;

-- ✅ OK (date filter satisfies huge-table rule)
SELECT measurement_source_value, AVG(value_as_number)
FROM cdm.measurement
WHERE measurement_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-07'
GROUP BY 1;

-- ✅ OK (CTE WHERE counts as a date filter)
WITH m AS (
  SELECT * FROM cdm.measurement WHERE _date_partition = DATE '2025-01-01'
)
SELECT COUNT(*) FROM m;

-- ❌ huge table, no date filter
SELECT * FROM cdm.measurement LIMIT 10;

-- ❌ banned function
SELECT * FROM read_parquet('/etc/passwd');

-- ❌ DDL
CREATE TABLE x AS SELECT 1;

-- ❌ multiple statements
SELECT 1; SELECT 2;
```

---

## 7. Joins you'll probably want

```sql
-- FHIR Patient ↔ surgery schedule (both anonymized with the same salt)
SELECT
  p.gender, p.year_of_birth_bin,
  COUNT(DISTINCT s.patient_id_anon) AS n_patients
FROM fhir.surgery_schedule s
JOIN fhir.patient p USING (patient_id_anon)
GROUP BY 1, 2;

-- CDM person ↔ measurement (BP example)
SELECT
  m.person_id, m.measurement_date,
  m.measurement_source_value, m.value_as_number, m.unit_source_value
FROM cdm.measurement m
WHERE m.measurement_source_value IN ('nibp_sbp', 'nibp_dbp')
  AND m.measurement_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-07'
  AND m.value_as_number IS NOT NULL
LIMIT 1000;

-- SNUH INSPIRE raw extension: ASA 3+ emergencies
SELECT o.op_id, o.department, o.asa, o.antype, o.icd10_pcs,
       o.orin_time, o.orout_time
FROM cdm.operations o
WHERE o.asa >= 3 AND o.emop = 1
  AND o._date_partition >= DATE '2025-01-01';
```

> ⚠️ **`fhir.*` and `cdm.*` do not join.** Two different datasets with
> different ID systems. Use one or the other per analysis.

---

## 8. Errors

```python
from khdp.supertable import (
    Client, PolicyRejected, QueryFailed, QueryTimeout,
    AuthenticationError, NotFound, SupertableError,
)

with Client() as c:
    try:
        c.query("DROP TABLE fhir.patient")
    except PolicyRejected as e:
        print("rejected:", e.errors)
```

| Exception | When |
|---|---|
| `AuthenticationError` | 401 — missing / invalid token |
| `PolicyRejected` | 400 — banned SQL, no date filter on a huge table |
| `NotFound` | 404 — unknown dataset / table |
| `QueryFailed` | DuckDB runtime error (e.g. `BinderException`) |
| `QueryTimeout` | exceeded the gateway's statement timeout |
| `SupertableError` | base class; also raised for over-limit / 5xx |

---

## 9. Minimal client example

```python
from khdp.supertable import Client

def query(sql: str, limit: int = 100) -> list[dict]:
    with Client() as c:
        return c.query(sql, limit=limit)

for row in query("SELECT gender, COUNT(*) AS n FROM cdm.person GROUP BY 1"):
    print(row["gender_concept_id"], row["n"])
```

For DataFrames:

```python
df = Client().df("""
    SELECT measurement_source_value, AVG(value_as_number) AS mean
    FROM cdm.measurement
    WHERE measurement_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-07'
      AND measurement_source_value IN ('nibp_sbp', 'nibp_dbp', 'hr', 'spo2')
    GROUP BY 1
""")
```

---

## 10. MCP — same tools, available to any MCP-aware LLM

Start the MCP server:

```bash
python -m khdp.mcp_server          # or: khdp-mcp
```

Four SuperTable tools are advertised alongside the four KHDP auth tools:

- `supertable_info(dataset?, table?)` → catalog manifest
- `supertable_stat(dataset?, table?, refresh?)` → zone-map stats
- `supertable_head(dataset, table, limit?)` → sample rows
- `supertable_query(sql, limit?, timeout_ms?)` → run SELECT

Configure in `~/.config/Claude/claude_desktop_config.json` or your
client's equivalent:

```json
{
  "mcpServers": {
    "khdp": {
      "command": "khdp-mcp",
      "env": {
        "SUPERTABLE_BASE_URL": "https://supertable.example.org",
        "SUPERTABLE_TOKEN": "..."
      }
    }
  }
}
```

For Claude Code specifically, also copy
`supertable/skills/supertable/SKILL.md` to
`~/.claude/skills/supertable/SKILL.md`. That file is curated for the
assistant: it tells Claude what SuperTable is, when to use each tool,
and how to interpret the responses.

---

## 11. Things this gateway does NOT do (yet)

- Write operations. Read-only forever for this dataset.
- Real-time push / WebSocket / subscriptions.
- Arrow Flight SQL fast-path for bulk transfer (planned).
- Per-column profile statistics — top-N values, histograms (planned).
- LLM-based query risk advisor (planned).
- AES-GCM signed download URLs (planned).

If a workflow needs any of the above, ask the SuperTable team.
