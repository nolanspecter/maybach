import sqlite3
from core.tools import tool


@tool
def run_sql(query: str, db_path: str = ":memory:") -> str:
    """Execute a SQL query and return results as a markdown table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)

        # cursor.description is None for non-SELECT statements (INSERT, UPDATE, etc.)
        if cursor.description is None:
            conn.commit()
            conn.close()
            return "Query executed successfully (no rows returned)."

        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "Query returned no results."

        # Build a GitHub-flavored markdown table the LLM can read back directly
        header  = "| " + " | ".join(columns) + " |"
        divider = "| " + " | ".join("---" for _ in columns) + " |"
        body    = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in rows)
        return "\n".join([header, divider, body])
    except Exception as e:
        return f"SQL error: {e}"


@tool
def list_tables(db_path: str = ":memory:") -> str:
    """List all tables in the SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # sqlite_master holds the schema for all objects in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return ", ".join(tables) if tables else "No tables found."
    except Exception as e:
        return f"Error: {e}"


@tool
def describe_table(table_name: str, db_path: str = ":memory:") -> str:
    """Describe the schema of a table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return f"Table '{table_name}' not found."
        lines = [f"- {r[1]} ({r[2]})" + (" NOT NULL" if r[3] else "") for r in rows]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"
