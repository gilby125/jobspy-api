# JobSpy API Test Suite

## Overview

This test suite provides comprehensive testing for the JobSpy API using **real data and actual functionality** rather than mocks. The tests are designed to validate the complete system behavior with actual JobSpy library integration, real database operations, and live API calls.

## Test Philosophy

Following the project's requirements:
- **No mocking** - All tests use real functionality
- **Real data** - Tests use actual data and live integrations
- **Complete validation** - Tests verify actual system behavior

## Test Structure

### Unit Tests (`tests/unit/`)

#### Service Tests (`tests/unit/services/`)
- **`test_job_service.py`** - Tests JobService with actual JobSpy library calls
  - Real job searches with live external APIs
  - Cache operations with actual Redis/memory cache
  - Parameter validation and filtering
  - Concurrent request handling
  - Error scenarios with real error conditions

### Integration Tests (`tests/integration/`)

#### API Integration (`tests/integration/api/`)
- **`test_api_real.py`** - Complete API endpoint testing
  - Real HTTP requests to API endpoints
  - JobSpy integration through API calls
  - Authentication flow testing
  - Response format validation (JSON/CSV)
  - Error handling and validation

#### Database Integration (`tests/integration/database/`)
- **`test_database_real.py`** - Real database operations
  - Actual database connections and transactions
  - CRUD operations with real data persistence
  - Relationship testing with actual foreign keys
  - Constraint validation
  - Complex queries with real data

### End-to-End Tests (`tests/e2e/`)

#### Complete Workflows (`tests/e2e/`)
- **`test_e2e_workflows_real.py`** - Full system workflows
  - Complete job search pipeline
  - Multi-site aggregation workflows
  - Caching behavior validation
  - CSV export workflows
  - Error handling workflows

### Performance Tests (`tests/performance/`)

#### Load and Performance (`tests/performance/`)
- **`test_performance_real.py`** - Real performance validation
  - Response time measurements
  - Concurrent request handling
  - Memory usage monitoring
  - Cache effectiveness testing
  - Load spike handling

## Test Data

### Fixtures (`tests/fixtures/`)
- **`sample_data.py`** - Real sample data for testing
  - Realistic job search parameters
  - Sample company and location data
  - Error scenarios for testing
  - No mocked responses - all real data structures

## Test Configuration

### Fixtures (`tests/conftest.py`)
- **Database fixtures** - Real PostgreSQL/TimescaleDB test database
- **Client fixtures** - Different client configurations
  - `client` - Basic test client with database override
  - `real_client` - Real integration client with cache enabled
  - `performance_client` - Optimized for performance testing
  - `authenticated_client` - Client with API key authentication

## Running Tests

### Prerequisites
```bash
# Install test dependencies (if available)
pip install pytest pytest-asyncio pytest-cov

# Or use system packages
sudo apt install python3-pytest
```

### Test Commands
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/unit/ -v                    # Unit tests only
python -m pytest tests/integration/ -v             # Integration tests only
python -m pytest tests/e2e/ -v                     # End-to-end tests only
python -m pytest tests/performance/ -v             # Performance tests only

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html

# Run specific test files
python -m pytest tests/unit/services/test_job_service.py -v
python -m pytest tests/integration/api/test_api_real.py -v
```

### Docker Testing
```bash
# Run tests in Docker environment
docker-compose exec jobspy-api python -m pytest tests/ -v

# Run with specific database
TEST_DATABASE_URL="postgresql://jobspy:jobspy_password@localhost:5432/test_jobspy" python -m pytest tests/
```

## Test Categories

### 1. Unit Tests
- **JobService** - Real JobSpy library integration
- **Cache operations** - Actual cache behavior
- **Data processing** - Real data filtering and sorting

### 2. Integration Tests
- **API endpoints** - Complete HTTP request/response cycle
- **Database operations** - Real data persistence
- **Authentication** - Actual API key validation

### 3. End-to-End Tests
- **Complete workflows** - Full system integration
- **Multi-component interaction** - Real data flow
- **Error handling** - Actual error scenarios

### 4. Performance Tests
- **Response times** - Real performance measurement
- **Concurrent load** - Actual concurrent request handling
- **Memory usage** - Real memory monitoring
- **Cache effectiveness** - Actual cache performance

## Expected Behavior

### Success Criteria
- All tests use real data and functionality
- No mocked external calls (where feasible)
- Tests validate actual system behavior
- Performance tests measure real response times
- Database tests use actual persistence

### Test Timeouts
- **Unit tests**: < 30 seconds each
- **Integration tests**: < 60 seconds each
- **E2E tests**: < 120 seconds each
- **Performance tests**: Variable based on external API performance

## Environment Requirements

### Required Environment Variables
```bash
TEST_DATABASE_URL=postgresql://jobspy:jobspy_password@localhost:5432/test_jobspy  # For database tests
REDIS_URL=redis://localhost:6379/15  # For cache tests (optional)
ENABLE_CACHE=true  # Enable caching for cache tests
ENABLE_API_KEY_AUTH=false  # Disable auth for easier testing
```

### External Dependencies
- **JobSpy library** - For real job scraping
- **External job APIs** - Indeed, LinkedIn, etc. (rate limits apply)
- **Database** - PostgreSQL/TimescaleDB for all tests (production-like)
- **Redis** - Optional for cache testing

## Test Maintenance

### Adding New Tests
1. Follow the real-data philosophy - no mocking
2. Use appropriate fixtures from `conftest.py`
3. Include both success and error scenarios
4. Add performance considerations
5. Document expected behavior

### Test Data Management
- Use realistic sample data from `fixtures/sample_data.py`
- Ensure test data represents real-world scenarios
- Update test data when API responses change

### Performance Considerations
- Tests may be slower due to real external API calls
- Network conditions affect test timing
- External API rate limits may affect test execution
- Consider running performance tests separately

## Continuous Integration

### CI/CD Considerations
- External API calls require network access
- Rate limiting may affect CI runs
- Consider test categorization for CI stages
- Use appropriate test data for CI environment

This test suite ensures the JobSpy API works correctly with real data and actual functionality, providing confidence in production deployment.