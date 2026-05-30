# Examples

Runnable code that uses the [`khdp`](https://pypi.org/project/khdp/) Python SDK against the KHDP REST API.

| Path | Auth | What it shows |
| --- | --- | --- |
| [`notebook/quickstart.ipynb`](./notebook/quickstart.ipynb) — [Open in Colab](https://colab.research.google.com/github/KoreaHealthDataPlatform/khdp-api/blob/main/examples/notebook/quickstart.ipynb) | optional | Five-section tour: install → search → detail → auth → list files → download. |
| [`python/01_anonymous_search.py`](./python/01_anonymous_search.py) | none | Search public datasets by keyword. |
| [`python/02_dataset_detail.py`](./python/02_dataset_detail.py) | none | Fetch metadata for a single dataset (`code` + optional `version`). |
| [`python/03_authenticated_download.py`](./python/03_authenticated_download.py) | API token | Pick the first Open dataset matching a query and stream its files to a local directory. |

## Setup

```bash
pip install khdp
```

For the authenticated script, set a personal API token (issued under *Settings → Account → API Token* at <https://khdp.net>):

```bash
export KHDP_TOKEN="khdp_pat_…"
```

## Run

```bash
python python/01_anonymous_search.py heart
python python/02_dataset_detail.py KHDP-OPEN-001
python python/03_authenticated_download.py heart --out ./data
```

See [`docs/REST_API.md`](../docs/REST_API.md) for every endpoint these scripts touch, and [`docs/quickstart.en.md`](../docs/quickstart.en.md) for a walkthrough that maps these scripts onto the CLI and MCP equivalents.
