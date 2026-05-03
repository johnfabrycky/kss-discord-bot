import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


async def ensure_tables_exist(db_url: str):
    """
    Connects directly to PostgreSQL to run schema setup scripts.
    Reads all .sql files from the docs/sql directory and executes them in order.
    """
    # 1. Dynamically find the project root.
    # This file is in /bot/utils, so we need to go up three levels to get to the root.
    base_dir = Path(__file__).resolve().parent.parent.parent
    sql_dir = base_dir / "docs" / "sql"

    if not sql_dir.exists():
        logger.error(f"SQL directory not found at {sql_dir}")
        return

    # 2. Get all .sql files and sort them alphabetically
    # Sorting is critical so 01_parking.sql runs before 02_meals.sql (prevents foreign key errors)
    sql_files = sorted(sql_dir.glob("*.sql"))

    if not sql_files:
        logger.warning(f"No .sql files found in {sql_dir}")
        return

    try:
        # Establish a direct, temporary connection to Postgres
        conn = await asyncpg.connect(db_url)

        # 3. Loop through and execute each file
        for file_path in sql_files:
            try:
                # Read the raw text from the SQL file
                sql_text = file_path.read_text(encoding="utf-8")

                # Execute the script
                await conn.execute(sql_text)
                logger.info(f"Successfully executed schema file: {file_path.name}")

            except Exception as file_err:
                logger.error(f"Error executing {file_path.name}: {file_err}")
                # You might want to 'break' or 'raise' here if a failed file should stop the rest
                raise

        logger.info("All database schemas verified successfully.")

    except Exception as e:
        logger.error(f"Failed to connect and verify database tables: {e}")

    finally:
        if 'conn' in locals():
            await conn.close()
