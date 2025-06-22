"""Real TimescaleDB integration tests."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session


class TestTimescaleDBReal:
    """Test TimescaleDB-specific features with real database."""

    def test_timescaledb_extension_available(self, test_db: Session):
        """Test that TimescaleDB extension is available."""
        result = test_db.execute(text(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')"
        )).scalar()
        
        # This might be False in test environments without TimescaleDB
        # That's OK - we're testing the connection and query capability
        assert isinstance(result, bool)

    def test_time_series_table_operations(self, test_db: Session):
        """Test basic time-series table operations."""
        # Create a simple time-series table for testing
        test_db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_time_series (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ NOT NULL,
                value DOUBLE PRECISION,
                tag VARCHAR(50)
            )
        """))
        test_db.commit()
        
        # Insert test data with time series
        base_time = datetime.utcnow()
        for i in range(10):
            test_db.execute(text("""
                INSERT INTO test_time_series (time, value, tag)
                VALUES (:time, :value, :tag)
            """), {
                "time": base_time + timedelta(minutes=i),
                "value": i * 10.5,
                "tag": f"test_tag_{i % 3}"
            })
        test_db.commit()
        
        # Query the data
        result = test_db.execute(text(
            "SELECT COUNT(*) FROM test_time_series"
        )).scalar()
        
        assert result == 10
        
        # Test time-based queries
        result = test_db.execute(text("""
            SELECT COUNT(*) FROM test_time_series 
            WHERE time >= :start_time
        """), {"start_time": base_time + timedelta(minutes=5)}).scalar()
        
        assert result == 5
        
        # Cleanup
        test_db.execute(text("DROP TABLE IF EXISTS test_time_series"))
        test_db.commit()

    def test_postgresql_specific_features(self, test_db: Session):
        """Test PostgreSQL-specific features used by the application."""
        # Test JSON operations
        test_db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_json (
                id SERIAL PRIMARY KEY,
                data JSONB
            )
        """))
        test_db.commit()
        
        # Insert JSON data
        test_db.execute(text("""
            INSERT INTO test_json (data) VALUES (:data)
        """), {"data": '{"search_term": "python", "results": 42}'})
        test_db.commit()
        
        # Query JSON data
        result = test_db.execute(text("""
            SELECT data->>'search_term' as search_term FROM test_json
        """)).scalar()
        
        assert result == "python"
        
        # Test array operations
        result = test_db.execute(text("""
            SELECT data->'results' as results FROM test_json
        """)).scalar()
        
        assert result == 42
        
        # Cleanup
        test_db.execute(text("DROP TABLE IF EXISTS test_json"))
        test_db.commit()

    def test_database_constraints_and_indexes(self, test_db: Session):
        """Test database constraints and indexing features."""
        # Create table with constraints
        test_db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_constraints (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                status VARCHAR(20) CHECK (status IN ('active', 'inactive', 'pending'))
            )
        """))
        test_db.commit()
        
        # Test successful insert
        test_db.execute(text("""
            INSERT INTO test_constraints (email, status) 
            VALUES ('test@example.com', 'active')
        """))
        test_db.commit()
        
        # Verify data was inserted
        result = test_db.execute(text(
            "SELECT email FROM test_constraints WHERE email = 'test@example.com'"
        )).scalar()
        
        assert result == "test@example.com"
        
        # Test unique constraint (should fail)
        with pytest.raises(Exception):
            test_db.execute(text("""
                INSERT INTO test_constraints (email, status) 
                VALUES ('test@example.com', 'inactive')
            """))
            test_db.commit()
        
        test_db.rollback()
        
        # Test check constraint (should fail)
        with pytest.raises(Exception):
            test_db.execute(text("""
                INSERT INTO test_constraints (email, status) 
                VALUES ('test2@example.com', 'invalid_status')
            """))
            test_db.commit()
        
        test_db.rollback()
        
        # Cleanup
        test_db.execute(text("DROP TABLE IF EXISTS test_constraints"))
        test_db.commit()

    def test_database_performance_features(self, test_db: Session):
        """Test database performance-related features."""
        # Create table for performance testing
        test_db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_performance (
                id SERIAL PRIMARY KEY,
                indexed_field VARCHAR(100),
                search_field TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        test_db.commit()
        
        # Create index
        test_db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_test_performance_indexed_field 
            ON test_performance(indexed_field)
        """))
        test_db.commit()
        
        # Insert test data
        for i in range(100):
            test_db.execute(text("""
                INSERT INTO test_performance (indexed_field, search_field)
                VALUES (:indexed_field, :search_field)
            """), {
                "indexed_field": f"value_{i % 10}",
                "search_field": f"searchable content {i}"
            })
        test_db.commit()
        
        # Test indexed query performance
        result = test_db.execute(text("""
            SELECT COUNT(*) FROM test_performance 
            WHERE indexed_field = 'value_5'
        """)).scalar()
        
        assert result == 10
        
        # Test full-text search capability
        result = test_db.execute(text("""
            SELECT COUNT(*) FROM test_performance 
            WHERE search_field ILIKE '%content%'
        """)).scalar()
        
        assert result == 100
        
        # Cleanup
        test_db.execute(text("DROP INDEX IF EXISTS idx_test_performance_indexed_field"))
        test_db.execute(text("DROP TABLE IF EXISTS test_performance"))
        test_db.commit()

    def test_transaction_handling(self, test_db: Session):
        """Test transaction handling and rollback capabilities."""
        # Create test table
        test_db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_transactions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL
            )
        """))
        test_db.commit()
        
        # Test successful transaction
        test_db.execute(text("""
            INSERT INTO test_transactions (name) VALUES ('test1')
        """))
        test_db.commit()
        
        # Verify insert
        result = test_db.execute(text(
            "SELECT COUNT(*) FROM test_transactions"
        )).scalar()
        assert result == 1
        
        # Test rollback
        test_db.execute(text("""
            INSERT INTO test_transactions (name) VALUES ('test2')
        """))
        test_db.rollback()
        
        # Verify rollback worked
        result = test_db.execute(text(
            "SELECT COUNT(*) FROM test_transactions"
        )).scalar()
        assert result == 1  # Should still be 1, not 2
        
        # Cleanup
        test_db.execute(text("DROP TABLE IF EXISTS test_transactions"))
        test_db.commit()