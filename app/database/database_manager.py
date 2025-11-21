"""
Database Manager
Handles database connections, sessions, and operations.
"""

from pathlib import Path
from typing import Optional, List, Type, TypeVar, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Engine

from app.database.models import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class DatabaseManager:
    """
    Manages database connections and provides session management.

    Supports both SQLite and PostgreSQL databases.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize database manager.

        Args:
            config: Database configuration dictionary
        """
        self.config = config or {}
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self.scoped_session_factory: Optional[scoped_session] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize database connection and create tables."""
        if self._initialized:
            logger.warning("Database already initialized")
            return

        try:
            # Get database configuration
            db_config = self.config.get('database', {})
            db_type = db_config.get('type', 'sqlite')

            # Create engine based on database type
            if db_type == 'sqlite':
                self._initialize_sqlite(db_config)
            elif db_type == 'postgresql':
                self._initialize_postgresql(db_config)
            else:
                raise ValueError(f"Unsupported database type: {db_type}")

            # Create session factory
            self.session_factory = sessionmaker(bind=self.engine)
            self.scoped_session_factory = scoped_session(self.session_factory)

            # Create tables
            Base.metadata.create_all(self.engine)

            self._initialized = True
            logger.info(f"Database initialized successfully ({db_type})")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _initialize_sqlite(self, config: dict) -> None:
        """
        Initialize SQLite database.

        Args:
            config: SQLite configuration
        """
        sqlite_config = config.get('sqlite', {})
        db_path = sqlite_config.get('path', 'database/intrusion_detection.db')

        # Create directory if it doesn't exist
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        # Create engine
        connection_string = f"sqlite:///{db_path}"
        self.engine = create_engine(
            connection_string,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
            echo=False
        )

        # Enable foreign keys for SQLite
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info(f"SQLite database initialized at: {db_path}")

    def _initialize_postgresql(self, config: dict) -> None:
        """
        Initialize PostgreSQL database.

        Args:
            config: PostgreSQL configuration
        """
        pg_config = config.get('postgresql', {})

        host = pg_config.get('host', 'localhost')
        port = pg_config.get('port', 5432)
        database = pg_config.get('database', 'intrusion_detection')
        user = pg_config.get('user', '')
        password = pg_config.get('password', '')

        if not user or not password:
            raise ValueError("PostgreSQL user and password must be configured")

        # Create engine
        connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self.engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            echo=False
        )

        logger.info(f"PostgreSQL database initialized: {database}@{host}:{port}")

    def get_session(self) -> Session:
        """
        Get a new database session.

        Returns:
            SQLAlchemy session

        Examples:
            >>> db = DatabaseManager(config)
            >>> db.initialize()
            >>> session = db.get_session()
            >>> # Use session for queries
            >>> session.close()
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        return self.session_factory()

    def get_scoped_session(self) -> scoped_session:
        """
        Get a thread-local scoped session.

        Returns:
            Scoped session

        Examples:
            >>> db = DatabaseManager(config)
            >>> db.initialize()
            >>> session = db.get_scoped_session()
            >>> # Use session for queries
            >>> session.remove()  # Remove thread-local session
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        return self.scoped_session_factory()

    @contextmanager
    def session_scope(self):
        """
        Provide a transactional scope for database operations.

        Yields:
            Database session

        Examples:
            >>> db = DatabaseManager(config)
            >>> db.initialize()
            >>> with db.session_scope() as session:
            ...     person = Person(name="John Doe")
            ...     session.add(person)
            ...     # Automatic commit on success, rollback on error
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            session.close()

    def add(self, obj: Any) -> None:
        """
        Add an object to the database.

        Args:
            obj: Database model instance to add
        """
        with self.session_scope() as session:
            session.add(obj)

    def add_all(self, objects: List[Any]) -> None:
        """
        Add multiple objects to the database.

        Args:
            objects: List of database model instances
        """
        with self.session_scope() as session:
            session.add_all(objects)

    def delete(self, obj: Any) -> None:
        """
        Delete an object from the database.

        Args:
            obj: Database model instance to delete
        """
        with self.session_scope() as session:
            session.delete(obj)

    def get_by_id(self, model: Type[T], id: int) -> Optional[T]:
        """
        Get an object by its ID.

        Args:
            model: Database model class
            id: Object ID

        Returns:
            Model instance or None if not found
        """
        with self.session_scope() as session:
            return session.query(model).filter(model.id == id).first()

    def get_all(self, model: Type[T], limit: Optional[int] = None) -> List[T]:
        """
        Get all objects of a specific model.

        Args:
            model: Database model class
            limit: Maximum number of results

        Returns:
            List of model instances
        """
        with self.session_scope() as session:
            query = session.query(model)
            if limit:
                query = query.limit(limit)
            return query.all()

    def query(self, model: Type[T]) -> Any:
        """
        Create a query for a model. Session must be managed separately.

        Args:
            model: Database model class

        Returns:
            SQLAlchemy query object
        """
        session = self.get_session()
        return session.query(model)

    def execute_raw(self, sql: str) -> Any:
        """
        Execute raw SQL query.

        Args:
            sql: SQL query string

        Returns:
            Query result
        """
        with self.session_scope() as session:
            return session.execute(sql)

    def vacuum(self) -> None:
        """
        Vacuum the database (SQLite only).
        Optimizes database file size and performance.
        """
        if self.engine.dialect.name == 'sqlite':
            try:
                with self.engine.connect() as conn:
                    conn.execute("VACUUM")
                logger.info("Database vacuumed successfully")
            except Exception as e:
                logger.error(f"Failed to vacuum database: {e}")

    def optimize(self) -> None:
        """
        Optimize database (analyze tables, rebuild indexes).
        """
        try:
            if self.engine.dialect.name == 'sqlite':
                with self.engine.connect() as conn:
                    conn.execute("ANALYZE")
                logger.info("Database optimized (SQLite ANALYZE)")
            elif self.engine.dialect.name == 'postgresql':
                with self.engine.connect() as conn:
                    conn.execute("ANALYZE")
                logger.info("Database optimized (PostgreSQL ANALYZE)")
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")

    def backup(self, backup_path: str) -> None:
        """
        Create a backup of the database (SQLite only).

        Args:
            backup_path: Path to save backup file
        """
        if self.engine.dialect.name != 'sqlite':
            logger.warning("Backup only supported for SQLite databases")
            return

        try:
            import sqlite3
            import shutil

            # Get current database path
            db_config = self.config.get('database', {})
            sqlite_config = db_config.get('sqlite', {})
            db_path = sqlite_config.get('path', 'database/intrusion_detection.db')

            # Create backup
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)

            # Use SQLite backup API for safe backup
            source = sqlite3.connect(db_path)
            dest = sqlite3.connect(backup_path)

            with dest:
                source.backup(dest)

            source.close()
            dest.close()

            logger.info(f"Database backed up to: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            raise

    def restore(self, backup_path: str) -> None:
        """
        Restore database from backup (SQLite only).

        Args:
            backup_path: Path to backup file
        """
        if self.engine.dialect.name != 'sqlite':
            logger.warning("Restore only supported for SQLite databases")
            return

        try:
            import shutil

            db_config = self.config.get('database', {})
            sqlite_config = db_config.get('sqlite', {})
            db_path = sqlite_config.get('path', 'database/intrusion_detection.db')

            # Close existing connections
            if self.engine:
                self.engine.dispose()

            # Restore from backup
            shutil.copy2(backup_path, db_path)

            # Reinitialize
            self._initialized = False
            self.initialize()

            logger.info(f"Database restored from: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            raise

    def close(self) -> None:
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")

    def __enter__(self):
        """Context manager entry."""
        if not self._initialized:
            self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global database instance
_db_instance: Optional[DatabaseManager] = None


def get_db(config: Optional[dict] = None) -> DatabaseManager:
    """
    Get global database instance.

    Args:
        config: Database configuration (only used on first call)

    Returns:
        DatabaseManager instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager(config)
        _db_instance.initialize()
    return _db_instance


if __name__ == "__main__":
    # Test database manager
    config = {
        'database': {
            'type': 'sqlite',
            'sqlite': {
                'path': 'test_database.db'
            }
        }
    }

    db = DatabaseManager(config)
    db.initialize()

    print(f"Database initialized: {db._initialized}")
    print(f"Engine: {db.engine}")

    # Test session
    with db.session_scope() as session:
        print(f"Session created: {session}")

    db.close()
    print("Database closed")
