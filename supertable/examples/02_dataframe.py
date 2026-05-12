"""SuperTable — pandas DataFrame example.

Install: ``pip install "khdp[pandas]"``  (or just ``pip install pandas``).

Computes mean blood pressure / heart rate / SpO2 by measurement type
for the first week of January 2025, against the synthetic CDM.
"""

from khdp.supertable import Client


def main() -> None:
    with Client() as c:
        df = c.df(
            """
            SELECT
              measurement_source_value AS metric,
              COUNT(*)                  AS n,
              AVG(value_as_number)      AS mean,
              MIN(value_as_number)      AS lo,
              MAX(value_as_number)      AS hi
            FROM cdm.measurement
            WHERE measurement_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-07'
              AND measurement_source_value IN ('nibp_sbp', 'nibp_dbp', 'hr', 'spo2')
              AND value_as_number IS NOT NULL
            GROUP BY 1
            ORDER BY n DESC
            """
        )
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
