"""SuperTable — keyset-chunked download.

The API is stateless: there is no `next_uri`. To stream more rows than
the per-request cap (50 000), chunk by a monotone key — typically the
table's primary key or a timestamp.

This example walks `cdm.operations` in 5 000-row pages, stopping when
the chunk is shorter than the page size.
"""

from khdp.supertable import Client

CHUNK = 5_000


def iter_operations_from(start_date: str):
    """Yield operations rows from start_date onward, op_id-ordered."""
    with Client() as c:
        last_op_id = 0
        while True:
            rows = c.query(
                f"""
                SELECT op_id, person_id, op_date_resolved, asa, emop,
                       department, antype, icd10_pcs
                FROM cdm.operations
                WHERE op_id > {last_op_id}
                  AND _date_partition >= DATE '{start_date}'
                ORDER BY op_id
                LIMIT {CHUNK}
                """,
                limit=CHUNK,
            )
            if not rows:
                break
            yield from rows
            if len(rows) < CHUNK:
                break
            last_op_id = rows[-1]["op_id"]


def main() -> None:
    total = 0
    for op in iter_operations_from("2025-01-01"):
        total += 1
        # process(op) ...
        if total % 10_000 == 0:
            print(f"streamed {total:,} operations")
    print(f"done, {total:,} operations total")


if __name__ == "__main__":
    main()
