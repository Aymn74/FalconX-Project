"""
Database management for PharmIntel system.
"""
import logging
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from pharmintel.core.models import Base
from pharmintel.config import DATABASE_URL, DATABASE_PATH

logger = logging.getLogger(__name__)


class Database:
    """Database manager for PharmIntel."""

    def __init__(self, database_url: Optional[str] = None, echo: bool = False):
        """
        Initialize database connection.

        Args:
            database_url: SQLAlchemy database URL. Uses config default if None.
            echo: Whether to echo SQL statements to stdout.
        """
        self.database_url = database_url or DATABASE_URL
        self.engine = create_engine(
            self.database_url,
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )

        # Enable foreign keys for SQLite
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info(f"Database initialized at: {DATABASE_PATH}")

    def create_all_tables(self):
        """Create all tables in the database."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("All database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def drop_all_tables(self):
        """Drop all tables from the database. Use with caution!"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Error dropping tables: {e}")
            raise

    def reset_database(self):
        """Reset database by dropping and recreating all tables."""
        logger.warning("Resetting database...")
        self.drop_all_tables()
        self.create_all_tables()
        logger.info("Database reset complete")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Usage:
            with db.get_session() as session:
                # Do database operations
                session.add(obj)
                session.commit()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """Get a session directly (caller must manage closing)."""
        return self.SessionLocal()

    def execute_raw_sql(self, sql: str) -> list:
        """
        Execute raw SQL query and return results.

        Args:
            sql: SQL query string

        Returns:
            List of result rows
        """
        with self.engine.connect() as conn:
            result = conn.execute(sql)
            return result.fetchall()

    def check_connection(self) -> bool:
        """
        Check if database connection is working.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    def get_table_info(self) -> dict:
        """
        Get information about all tables in the database.

        Returns:
            Dictionary with table names as keys and row counts as values
        """
        info = {}
        try:
            with self.get_session() as session:
                for table_name in Base.metadata.tables.keys():
                    table = Base.metadata.tables[table_name]
                    count = session.query(table).count()
                    info[table_name] = count
        except Exception as e:
            logger.error(f"Error getting table info: {e}")
            info["error"] = str(e)

        return info

    def backup_database(self, backup_path: str):
        """
        Create a backup of the SQLite database.

        Args:
            backup_path: Path where backup should be saved
        """
        import shutil

        try:
            shutil.copy2(DATABASE_PATH, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise

    def vacuum_database(self):
        """Vacuum the database to reclaim space and optimize."""
        try:
            with self.engine.connect() as conn:
                conn.execute("VACUUM")
            logger.info("Database vacuumed successfully")
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")
            raise


# Global database instance
_db_instance: Optional[Database] = None


def get_database(reset: bool = False) -> Database:
    """
    Get or create the global database instance.

    Args:
        reset: If True, reset the database (drop and recreate tables)

    Returns:
        Database instance
    """
    global _db_instance

    if _db_instance is None:
        _db_instance = Database()
        _db_instance.create_all_tables()

    if reset:
        _db_instance.reset_database()

    return _db_instance


def init_database(reset: bool = False):
    """
    Initialize the database.

    Args:
        reset: If True, reset the database (drop and recreate tables)
    """
    db = get_database(reset=reset)
    logger.info("Database initialization complete")
    return db


# Dependency injection for FastAPI
def get_db_session():
    """
    Dependency for FastAPI to get database sessions.

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db_session)):
            # Use db session
    """
    db = get_database()
    session = db.get_session_direct()
    try:
        yield session
    finally:
        session.close()
