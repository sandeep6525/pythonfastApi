import sqlite3
import getpass
import psycopg


SQLITE_DB = "levelupwards.db"


def quote_identifier(name):
    """Safely quote PostgreSQL identifiers."""
    return '"' + name.replace('"', '""') + '"'


def get_sqlite_tables(sqlite_conn):
    cursor = sqlite_conn.cursor()

    rows = cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    return [row[0] for row in rows]


def create_table_in_postgres(pg_conn, sqlite_conn, table_name):
    cursor = sqlite_conn.cursor()

    # Get the original CREATE TABLE statement
    row = cursor.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,)
    ).fetchone()

    if not row or not row[0]:
        raise RuntimeError(f"Could not find schema for table: {table_name}")

    create_sql = row[0]

    print(f"Creating table: {table_name}")

    with pg_conn.cursor() as pg_cursor:
        pg_cursor.execute(create_sql)

    pg_conn.commit()


def copy_table_data(pg_conn, sqlite_conn, table_name):
    sqlite_cursor = sqlite_conn.cursor()

    # Get column names
    columns = [
        row[1]
        for row in sqlite_cursor.execute(
            f"PRAGMA table_info({quote_identifier(table_name)})"
        ).fetchall()
    ]

    if not columns:
        return 0

    # Get all SQLite rows
    rows = sqlite_cursor.execute(
        f"SELECT * FROM {quote_identifier(table_name)}"
    ).fetchall()

    if not rows:
        print(f"  No data in {table_name}")
        return 0

    quoted_columns = ", ".join(
        quote_identifier(column)
        for column in columns
    )

    placeholders = ", ".join(
        ["%s"] * len(columns)
    )

    insert_sql = f"""
        INSERT INTO {quote_identifier(table_name)}
        ({quoted_columns})
        VALUES ({placeholders})
    """

    with pg_conn.cursor() as pg_cursor:
        pg_cursor.executemany(insert_sql, rows)

    pg_conn.commit()

    print(f"  Copied {len(rows)} rows")

    return len(rows)


def main():
    print("=" * 60)
    print("LEVELUPWARDS SQLite → Neon PostgreSQL Migration")
    print("=" * 60)

    print("\nOpening SQLite database...")

    sqlite_conn = sqlite3.connect(SQLITE_DB)

    tables = get_sqlite_tables(sqlite_conn)

    print(f"\nFound {len(tables)} tables:")

    for table in tables:
        print(f"  - {table}")

    print("\n" + "-" * 60)

    print("\nPaste your Neon connection string below.")
    print("The password will NOT be displayed while typing/pasting.\n")

    database_url = getpass.getpass("Neon connection string: ")

    if not database_url.startswith("postgresql://"):
        raise ValueError(
            "The connection string should start with postgresql://"
        )

    print("\nConnecting to Neon...")

    pg_conn = psycopg.connect(database_url)

    print("Neon connection successful!")

    print("\nCreating tables...")

    for table in tables:
        create_table_in_postgres(
            pg_conn,
            sqlite_conn,
            table
        )

    print("\nCopying data...")

    total_rows = 0

    for table in tables:
        total_rows += copy_table_data(
            pg_conn,
            sqlite_conn,
            table
        )

    sqlite_conn.close()
    pg_conn.close()

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETED SUCCESSFULLY")
    print("=" * 60)

    print(f"\nTables migrated: {len(tables)}")
    print(f"Total rows migrated: {total_rows}")


if __name__ == "__main__":
    main()