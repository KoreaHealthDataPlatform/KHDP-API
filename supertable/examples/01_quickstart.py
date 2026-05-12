"""SuperTable — quickstart.

Run with::

    SUPERTABLE_BASE_URL=https://supertable.example.org \
    SUPERTABLE_TOKEN=... \
    python 01_quickstart.py
"""

from khdp.supertable import Client


def main() -> None:
    with Client() as c:
        # 1. What datasets are exposed?
        print("datasets:", c.datasets())

        # 2. What columns does fhir.patient have?
        for col in c.columns("fhir", "patient"):
            print(f"  {col['name']:30s} {col['type']}")

        # 3. Peek at the actual data.
        print("\nsample patients:")
        for row in c.head("fhir", "patient", limit=3):
            print(" ", row)

        # 4. A real query.
        print("\ngender distribution:")
        for row in c.query(
            "SELECT gender, COUNT(*) AS n FROM fhir.patient GROUP BY 1 ORDER BY n DESC"
        ):
            print(" ", row)


if __name__ == "__main__":
    main()
