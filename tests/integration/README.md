# Deal Sniper AI Integration Tests

Comprehensive integration tests for the Deal Sniper AI Platform, testing the complete pipeline from crawling to analytics.

## Test Structure

### 1. `conftest.py` - Shared Pytest Fixtures
Provides shared fixtures for:
- **Database sessions**: In-memory SQLite for testing
- **Mocked external services**: Playwright, Redis, Celery, asyncpg
- **Configuration loading**: Test configuration with mocked values
- **API client**: FastAPI TestClient with mocked dependencies
- **Test data factories**: Sample products, deals, affiliate links, etc.

### 2. `test_full_pipeline.py` - Complete Pipeline Tests
Tests the end-to-end flow:
- **Crawler**: Product extraction and price history creation
- **Price Watch Grid**: Price change detection
- **Anomaly Detection**: Statistical outlier identification
- **Coupon Engine**: Coupon detection and validation
- **Glitch Detection**: Pricing error identification
- **Deal Scoring**: Weighted scoring algorithm
- **Affiliate Conversion**: URL conversion and tracking
- **Posting Engine**: Multi-platform posting
- **Growth Engine**: Engagement analysis and virality detection
- **Analytics Tracking**: Performance metrics collection

### 3. `test_database_operations.py` - Database Integration Tests
Tests database models, relationships, and queries:
- **Model validation**: All SQLAlchemy models
- **Relationships**: Foreign key constraints and cascades
- **Complex queries**: Analytics, aggregations, filtering
- **Transactions**: ACID properties and error handling
- **Performance**: Index usage and query optimization

### 4. `test_celery_tasks.py` - Celery Task Integration Tests
Tests distributed task processing:
- **Task configuration**: Routing, queues, serialization
- **Scheduling**: Celery Beat periodic tasks
- **Error handling**: Retries, timeouts, failure recovery
- **Task chains**: Orchestration between modules
- **Queue isolation**: Proper task routing to dedicated queues

### 5. `test_api_endpoints.py` - API Integration Tests
Tests FastAPI endpoints and integration:
- **Health checks**: Service status monitoring
- **Deal management**: CRUD operations for deals
- **Task management**: Celery task status and triggering
- **Configuration**: Secure configuration access
- **Dashboard**: Real-time monitoring interface
- **Error handling**: Proper HTTP status codes and validation

## Running Tests

### Prerequisites
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock httpx sqlalchemy aiosqlite
```

### Running All Tests
```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with coverage
pytest tests/integration/ --cov=deal_sniper_ai --cov-report=html
```

### Running Specific Test Files
```bash
# Run full pipeline tests
pytest tests/integration/test_full_pipeline.py -v

# Run database tests
pytest tests/integration/test_database_operations.py -v

# Run Celery tests
pytest tests/integration/test_celery_tasks.py -v

# Run API tests
pytest tests/integration/test_api_endpoints.py -v
```

### Running with Different Options
```bash
# Run with detailed output
pytest tests/integration/ -v --tb=short

# Run specific test class
pytest tests/integration/test_full_pipeline.py::TestFullPipeline -v

# Run specific test method
pytest tests/integration/test_full_pipeline.py::TestFullPipeline::test_complete_pipeline_flow -v
```

## Test Configuration

### Environment Variables
Tests use a dedicated test configuration (`TEST_CONFIG` in `conftest.py`):
- **Database**: In-memory SQLite (no external dependencies)
- **Redis**: Mocked (no Redis server required)
- **Celery**: Mocked tasks and workers
- **Playwright**: Mocked browser interactions

### Mocked Services
All external services are mocked:
- **Playwright**: Mock browser, page, and responses
- **Redis**: Mock client with simulated operations
- **Celery**: Mock app, tasks, and results
- **asyncpg**: Mock database connections
- **External APIs**: All external API calls are mocked

### Test Data
Fixtures provide reusable test data:
- **Products**: Sample products with various attributes
- **Price History**: Historical price data for analysis
- **Deal Candidates**: Potential deals in different states
- **Posted Deals**: Published deals with performance metrics
- **Affiliate Links**: Converted URLs with tracking
- **Coupon Codes**: Validated coupon codes

## Test Coverage

### Module Coverage
- [x] `deal_sniper_ai/crawler/` - E-commerce crawler
- [x] `deal_sniper_ai/price_watch_grid/` - Price monitoring
- [x] `deal_sniper_ai/anomaly_engine/` - Anomaly detection
- [x] `deal_sniper_ai/coupon_engine/` - Coupon detection
- [x] `deal_sniper_ai/glitch_detector/` - Glitch detection
- [x] `deal_sniper_ai/deal_scorer/` - Deal scoring
- [x] `deal_sniper_ai/affiliate_engine/` - Affiliate conversion
- [x] `deal_sniper_ai/posting_engine/` - Multi-platform posting
- [x] `deal_sniper_ai/growth_engine/` - Community growth
- [x] `deal_sniper_ai/analytics_engine/` - Analytics tracking
- [x] `deal_sniper_ai/scheduler/` - Celery task orchestration
- [x] `deal_sniper_ai/api/` - FastAPI application
- [x] `deal_sniper_ai/database/` - Database models and session

### Integration Points Tested
1. **Crawler → Database**: Product and price history storage
2. **Price Watch → Anomaly Detection**: Statistical analysis
3. **Coupon Engine → Deal Scoring**: Score component integration
4. **Affiliate Engine → Posting Engine**: URL conversion for posting
5. **Posting Engine → Growth Engine**: Engagement tracking
6. **Growth Engine → Analytics**: Performance metric collection
7. **API → All Modules**: Endpoint integration with business logic
8. **Celery → All Modules**: Distributed task execution

## Test Design Patterns

### 1. Dependency Injection
All external dependencies are injected via fixtures, allowing easy mocking.

### 2. Arrange-Act-Assert
Clear test structure with setup, execution, and verification phases.

### 3. Parameterized Testing
Where applicable, tests use parameterization for different scenarios.

### 4. Async/Await Support
Full support for asynchronous operations with `pytest-asyncio`.

### 5. Comprehensive Mocking
External services are thoroughly mocked to ensure test isolation.

## Adding New Tests

### 1. New Module Integration
```python
# Example: Adding tests for a new module
def test_new_module_integration(mock_new_module, test_db_session):
    # Arrange
    test_data = {...}

    # Act
    result = await new_module.process(test_data)

    # Assert
    assert result["success"] is True
    assert "expected_field" in result
```

### 2. New API Endpoint
```python
# Example: Adding tests for a new endpoint
def test_new_endpoint(api_client, mock_dependencies):
    # Act
    response = api_client.get("/api/new-endpoint")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

### 3. New Database Model
```python
# Example: Adding tests for a new model
@pytest.mark.asyncio
async def test_new_model(test_db_session):
    # Arrange
    new_instance = NewModel(...)

    # Act
    test_db_session.add(new_instance)
    await test_db_session.commit()

    # Assert
    assert new_instance.id is not None
    assert new_instance.created_at is not None
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Integration Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-mock
      - name: Run integration tests
        run: pytest tests/integration/ -v --cov=deal_sniper_ai --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

1. **Async Test Failures**
   - Ensure `@pytest.mark.asyncio` decorator is used
   - Use `pytest-asyncio` fixture for event loop

2. **Mock Not Working**
   - Check import paths match exactly
   - Use `unittest.mock.patch` with correct target

3. **Database Session Issues**
   - Use `test_db_session` fixture for async sessions
   - Commit changes before assertions

4. **Configuration Loading**
   - Tests use `TEST_CONFIG` in `conftest.py`
   - External config files are mocked

### Debugging Tips
```bash
# Run tests with debug output
pytest tests/integration/ -v -s

# Run specific test with detailed traceback
pytest tests/integration/test_file.py::TestClass::test_method -v --tb=long

# Use pdb for debugging
import pdb; pdb.set_trace()  # Add to test code
```

## Performance Considerations

### Test Optimization
- **Isolation**: Each test runs in isolation with fresh fixtures
- **Mocking**: External services are mocked for speed
- **Database**: In-memory SQLite for fast database operations
- **Parallelization**: Tests can run in parallel with `pytest-xdist`

### Resource Usage
- **Memory**: Minimal due to mocking and in-memory database
- **CPU**: Lightweight, no browser automation
- **Network**: No external network calls
- **Disk**: Temporary files cleaned up automatically

## Security Considerations

### Test Data Security
- No real API keys or credentials in tests
- Sensitive data is mocked or uses test values
- Database uses isolated test instances

### Network Isolation
- All external calls are mocked
- No actual HTTP requests during tests
- No dependency on external services

## Maintenance

### Keeping Tests Updated
1. **When adding new features**: Add corresponding integration tests
2. **When changing APIs**: Update affected test cases
3. **Regular review**: Review test coverage quarterly
4. **Dependency updates**: Update test dependencies with main codebase

### Test Quality Metrics
- **Coverage**: Aim for >80% integration test coverage
- **Speed**: Complete test suite should run in <2 minutes
- **Reliability**: Tests should be deterministic and repeatable
- **Maintainability**: Clear, well-documented test cases