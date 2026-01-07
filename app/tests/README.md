# Dashboard API Tests

## Files

### `test_dashboard.py`
Tests dashboard CRUD operations:
- Create dashboard
- Publish dashboard  
- Update dashboard details
- Edit dashboard content
- Delete dashboard draft
- Delete dashboard

### `test_features.py`
Tests features operations:
- Share operations (multiple + single)
- Schedule operations (multiple + single) 
- Integration operations (multiple + single)

## Usage

### 1. Set Authentication Token
Replace `YOUR_AUTH_TOKEN_HERE` with your actual authentication token in both files.

### 2. Set Dashboard ID (for features test)
Replace `YOUR_DASHBOARD_ID_HERE` in `test_features.py` with an existing dashboard ID.

### 3. Run Tests
```bash
# Run dashboard tests
python test_dashboard.py

# Run features tests (requires existing dashboard)
python test_features.py
```

## Requirements
- Python 3.7+
- httpx library (`pip install httpx`)
- Dashboard API running on `localhost:8021`
- Valid authentication token

## Notes
- Tests automatically cleanup created resources
- Include proper error handling
- Use async/await patterns for performance
- Tests are independent and can be run separately