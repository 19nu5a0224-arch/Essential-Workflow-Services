# Dashboard Workflow API - Project Documentation

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Project Structure](#project-structure)
- [Core Features](#core-features)
- [API Endpoints Mapping](#api-endpoints-mapping)
  - [Dashboard Routes](#dashboard-routes)
  - [Comment Routes](#comment-routes)
  - [Widget Locking Routes](#widget-locking-routes)
  - [n8n Integration Routes](#n8n-integration-routes)
  - [Feature Routes](#feature-routes)
- [Codebase Architecture Pattern](#codebase-architecture-pattern)
- [Configuration](#configuration)
- [Development Guide](#development-guide)
- [Deployment](#deployment)
- [Monitoring & Debugging](#monitoring--debugging)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Support](#support)

## Overview

The Dashboard Workflow API is a comprehensive FastAPI-based application designed for managing dashboards, workflow integrations, and collaborative features. This project provides a robust backend system with features like dashboard management, version control, commenting system, widget locking, and integration with n8n workflows.

## Quick Start

### Prerequisites

- Python 3.14+
- PostgreSQL database
- Redis (for caching, optional)
- n8n instance (for workflow integrations)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd dashboard_workflow
```

2. **Set up Python environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment configuration**
Create a `.env` file in the project root:
```env
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/dashboard_db
DEBUG=false
LOG_LEVEL=INFO
N8N_API_KEY=your_n8n_api_key
N8N_BASE_URL=http://your-n8n-instance:5678/api/v1
```

5. **Database setup**
```bash
# The application will automatically create tables on first run
python -m app.main
```

### Running the Application

**Development mode:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Project Structure

```
dashboard_workflow/
├── app/                           # Main application package
│   ├── auth/                      # Authentication modules
│   ├── core/                      # Core configuration and utilities
│   │   ├── config.py              # Application settings
│   │   ├── database.py            # Database connection management
│   │   ├── enums.py               # Application enums
│   │   └── logging.py             # Logging configuration
│   ├── dbmodels/                  # Database models
│   ├── monitoring/                # Observability and metrics
│   ├── routers/                   # API route handlers
│   │   ├── dashboard_routers.py   # Dashboard management endpoints
│   │   ├── feature_routers.py     # Feature flag endpoints
│   │   ├── comment_routers.py     # Comment system endpoints
│   │   ├── n8n_workflows_router.py # n8n integration endpoints
│   │   ├── widget_locking_router.py # Widget locking endpoints
│   │   └── internal_router.py     # Internal API endpoints
│   ├── schemas/                   # Pydantic schemas for data validation
│   ├── services/                  # Business logic services
│   ├── utils/                     # Utility functions
│   ├── main.py                    # Application entry point
│   └── __init__.py
├── tests/                         # Test suite
├── pyproject.toml                # Project configuration
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Core Features

### Dashboard Management
- Create, read, update, and delete dashboards
- Version control with draft/publish workflow
- Content and metadata updates
- Pagination and filtering

### Workflow Integration (n8n)
- Execute n8n workflows via API
- Workflow status tracking
- Asynchronous workflow execution
- Error handling and retry mechanisms

### Comment System
- Threaded comments on dashboards
- Real-time updates
- User mentions and notifications
- Comment moderation

### Widget Locking
- Collaborative editing prevention
- Real-time lock management
- Automatic lock cleanup
- Conflict resolution

### Observability & Monitoring
- OpenTelemetry integration
- Prometheus metrics
- Request tracing
- System health monitoring

## API Endpoints Mapping

### Dashboard Routes

#### Create Dashboard
- **Endpoint**: `POST /dashboards/create_dashboard`
- **Router**: `dashboard_workflow/app/routers/dashboard_routers.py` - `create_dashboard()`
- **Service**: `dashboard_workflow/app/services/dashboard_service.py` - `DashboardService.create_dashboard()`
  - Validates user permissions via `PermissionService.check_create_dashboard()`
  - Creates dashboard using CoreDashboard operations
  - Logs activity and clears cache
- **Codebase**: `dashboard_workflow/app/codebase/dashboards.py` - `CoreDashboard.create_dashboard()`
  - Processes widget content and generates UUIDs for widgets
  - Creates dashboard and initial draft version
  - Handles database transactions

#### Get All Dashboards
- **Endpoint**: `GET /dashboards/get_all_dashboards`
- **Router**: `dashboard_workflow/app/routers/dashboard_routers.py` - `get_all_dashboards()`
- **Service**: `dashboard_workflow/app/services/dashboard_service.py` - `DashboardService.get_all_dashboards()`
  - Retrieves dashboards with pagination support
  - Includes user's dashboards, shared dashboards, and shared with user
- **Codebase**: `dashboard_workflow/app/codebase/dashboards.py` - `CoreDashboard.get_all_dashboards()`
  - Complex query combining ownership and sharing logic
  - Handles pagination and filtering

#### Get Dashboard by ID
- **Endpoint**: `GET /dashboards/getdashboardbyid/{dashboard_id}`
- **Router**: `dashboard_workflow/app/routers/dashboard_routers.py` - `get_dashboard_by_id()`
- **Service**: `dashboard_workflow/app/services/dashboard_service.py` - `DashboardService.get_dashboard_by_id()`
  - Supports version-specific content retrieval
  - Includes draft and published version handling
- **Codebase**: `dashboard_workflow/app/codebase/dashboards.py` - `CoreDashboard.get_dashboard_by_id()`
  - Retrieves dashboard with version control
  - Handles draft and published version logic

#### Update Dashboard Details
- **Endpoint**: `PATCH /dashboards/{dashboard_id}/update_details`
- **Router**: `dashboard_workflow/app/routers/dashboard_routers.py` - `update_dashboard_details()`
- **Service**: `dashboard_workflow/app/services/dashboard_service.py` - `DashboardService.update_dashboard_details()`
  - Updates dashboard metadata (name, description, etc.)
  - Validates user permissions for modification
- **Codebase**: `dashboard_workflow/app/codebase/dashboards.py` - `CoreDashboard.update_dashboard_details()`
  - Handles database updates and validation

#### Update Dashboard Content
- **Endpoint**: `PATCH /dashboards/{dashboard_id}/edit`
- **Router**: `dashboard_workflow/app/routers/dashboard_routers.py` - `update_dashboard_content()`
- **Service**: `dashboard_workflow/app/services/dashboard_service.py` - `DashboardService.update_dashboard_content()`
  - Updates widget content and layout
  - Creates or updates draft version
- **Codebase**: `dashboard_workflow/app/codebase/dashboards.py` - `CoreDashboard.update_dashboard_content()`
  - Processes widget content updates
  - Maintains draft version history

#### Publish Dashboard
- **Endpoint**: `POST /dashboards/{dashboard_id}/publish`
- **Router**: `dashboard_workflow/app/routers/dashboard_routers.py` - `publish_dashboard()`
- **Service**: `dashboard_workflow/app/services/dashboard_service.py` - `DashboardService.publish_dashboard()`
  - Archives previous published version
  - Promotes draft to published status
- **Codebase**: `dashboard_workflow/app/codebase/dashboards.py` - `CoreDashboard.publish_dashboard()`
  - Handles version publishing logic
  - Manages version archiving

#### Delete Dashboard
- **Endpoint**: `DELETE /dashboards/{dashboard_id}`
- **Router**: `dashboard_workflow/app/routers/dashboard_routers.py` - `delete_dashboard()`
- **Service**: `dashboard_workflow/app/services/dashboard_service.py` - `DashboardService.delete_dashboard()`
  - Supports draft version deletion
  - Soft delete implementation
- **Codebase**: `dashboard_workflow/app/codebase/dashboards.py` - `CoreDashboard.delete_dashboard()`
  - Handles soft delete logic
  - Manages version cleanup

### Comment Routes

#### Create Comment
- **Endpoint**: `POST /comments/{entity_type}/{entity_id}/{comment_type}`
- **Router**: `dashboard_workflow/app/routers/comment_routers.py` - `create_comment()`
- **Service**: `dashboard_workflow/app/services/comment_service.py` - `CommentService.create_comment()`
  - Supports root comments and replies
  - Handles mentions and notifications
- **Codebase**: `dashboard_workflow/app/codebase/comments.py` - `CoreComments.create_comment()`
  - Implements threaded comment system
  - Manages comment hierarchy

#### Get Comments
- **Endpoint**: `GET /comments/{entity_type}/{entity_id}`
- **Router**: `dashboard_workflow/app/routers/comment_routers.py` - `get_comments()`
- **Service**: `dashboard_workflow/app/services/comment_service.py` - `CommentService.get_hierarchical_comments()`
  - Returns hierarchical comment tree with nested replies
  - Supports pagination and depth control
- **Codebase**: `dashboard_workflow/app/codebase/comments.py` - `CoreComments.get_hierarchical_comments()`
  - Implements recursive comment fetching
  - Handles reply depth limits

#### Update Comment
- **Endpoint**: `PUT /comments/{comment_id}`
- **Router**: `dashboard_workflow/app/routers/comment_routers.py` - `update_comment()`
- **Service**: `dashboard_workflow/app/services/comment_service.py` - `CommentService.update_comment()`
  - Only allows comment author to update
  - Preserves edit history
- **Codebase**: `dashboard_workflow/app/codebase/comments.py` - `CoreComments.update_comment()`
  - Handles content updates with validation

#### Like/Comment
- **Endpoint**: `POST /comments/{comment_id}/like`
- **Router**: `dashboard_workflow/app/routers/comment_routers.py` - `like_comment()`
- **Service**: `dashboard_workflow/app/services/comment_service.py` - `CommentService.toggle_comment_like()`
  - Toggle-like functionality
  - Real-time like count updates
- **Codebase**: `dashboard_workflow/app/codebase/comments.py` - `CoreComments.toggle_comment_like()`
  - Implements like/unlike logic

#### Delete Comment
- **Endpoint**: `DELETE /comments/{comment_id}`
- **Router**: `dashboard_workflow/app/routers/comment_routers.py` - `delete_comment()`
- **Service**: `dashboard_workflow/app/services/comment_service.py` - `CommentService.delete_comment()`
  - Soft delete preserving thread integrity
  - Author-only deletion
- **Codebase**: `dashboard_workflow/app/codebase/comments.py` - `CoreComments.delete_comment()`
  - Handles soft delete with thread preservation

### Widget Locking Routes

#### Acquire Widget Lock
- **Endpoint**: `POST /collaboration/dashboards/{dashboard_id}/widgets/lock`
- **Router**: `dashboard_workflow/app/routers/widget_locking_router.py` - `acquire_widget_lock()`
- **Service**: `dashboard_workflow/app/services/widget_locking_service.py` - `WidgetLockingService.acquire_widget_lock()`
  - Acquires exclusive widget editing lock
  - Handles concurrent access conflicts
- **Codebase**: `dashboard_workflow/app/codebase/widget_locking.py` - `CoreWidgetLocking.acquire_widget_lock()`
  - Implements distributed locking mechanism

#### Refresh Widget Lock
- **Endpoint**: `POST /collaboration/dashboards/{dashboard_id}/widgets/heartbeat`
- **Router**: `dashboard_workflow/app/routers/widget_locking_router.py` - `refresh_widget_lock()`
- **Service**: `dashboard_workflow/app/services/widget_locking_service.py` - `WidgetLockingService.refresh_widget_lock()`
  - Extends lock expiration via heartbeat
  - Optimized for frequent polling
- **Codebase**: `dashboard_workflow/app/codebase/widget_locking.py` - `CoreWidgetLocking.refresh_widget_lock()`
  - Handles lock lifecycle management

#### Release Widget Lock
- **Endpoint**: `DELETE /collaboration/dashboards/{dashboard_id}/widgets/lock`
- **Router**: `dashboard_workflow/app/routers/widget_locking_router.py` - `release_widget_lock()`
- **Service**: `dashboard_workflow/app/services/widget_locking_service.py` - `WidgetLockingService.release_widget_lock()`
  - Explicit lock release by owner
  - Owner-only release validation
- **Codebase**: `dashboard_workflow/app/codebase/widget_locking.py` - `CoreWidgetLocking.release_widget_lock()`
  - Implements lock cleanup logic

#### Get Widget Lock Status
- **Endpoint**: `GET /collaboration/dashboards/{dashboard_id}/widgets/{widget_id}/status`
- **Router**: `dashboard_workflow/app/routers/widget_locking_router.py` - `get_widget_lock_status()`
- **Service**: `dashboard_workflow/app/services/widget_locking_service.py` - `WidgetLockingService.get_widget_lock_status()`
  - Optimized for high-frequency polling
  - Returns lock ownership and expiration
- **Codebase**: `dashboard_workflow/app/codebase/widget_locking.py` - `CoreWidgetLocking.get_widget_lock_status()`
  - Fast lock status retrieval

### n8n Integration Routes

#### Get User Workflows
- **Endpoint**: `GET /n8n-workflows/`
- **Router**: `dashboard_workflow/app/routers/n8n_workflows_router.py` - `get_user_workflows()`
- **Service**: `dashboard_workflow/app/services/n8n_operations_service.py` - `N8NOperationsService.get_user_workflows()`
  - Retrieves workflows user has permission to access
  - Supports pagination and execution history
- **Codebase**: `dashboard_workflow/app/codebase/n8n_operations.py` - `CoreN8NOperations.get_user_workflows()`
  - Integrates with n8n API
  - Handles workflow filtering by permissions

#### Get Workflow by ID
- **Endpoint**: `GET /n8n-workflows/{workflow_id}`
- **Router**: `dashboard_workflow/app/routers/n8n_workflows_router.py` - `get_workflow_by_id()`
- **Service**: `dashboard_workflow/app/services/n8n_operations_service.py` - `N8NOperationsService.get_workflow_by_id()`
  - Retrieves specific workflow with detailed information
  - Includes execution history if requested
- **Codebase**: `dashboard_workflow/app/codebase/n8n_operations.py` - `CoreN8NOperations.get_workflow_by_id()`
  - Detailed workflow information retrieval

### Feature Routes

#### Share Management
- **Endpoints**: `GET/POST/PATCH/DELETE /features/shares`
- **Router**: `dashboard_workflow/app/routers/feature_routers.py`
- **Service**: `dashboard_workflow/app/services/features_service.py`
- **Codebase**: `dashboard_workflow/app/codebase/features.py`

#### Schedule Management
- **Endpoints**: `GET/POST/PATCH/DELETE /features/schedules`
- **Router**: `dashboard_workflow/app/routers/feature_routers.py`
- **Service**: `dashboard_workflow/app/services/features_service.py`
- **Codebase**: `dashboard_workflow/app/codebase/features.py`

#### Integration Management
- **Endpoints**: `GET/POST/PATCH/DELETE /features/integrations`
- **Router**: `dashboard_workflow/app/routers/feature_routers.py`
- **Service**: `dashboard_workflow/app/services/features_service.py`
- **Codebase**: `dashboard_workflow/app/codebase/features.py`

## Codebase Architecture Pattern

The application follows a **Layered Architecture** with clear separation of concerns:

```
Request Flow: HTTP Request → Router → Service → Codebase → Database
```

### Architecture Layers

1. **Router Layer** (`app/routers/`)
   - HTTP endpoint handlers
   - Request validation and serialization
   - Authentication middleware integration
   - Error handling translation

2. **Service Layer** (`app/services/`)
   - Business logic and use cases
   - Permission checking and validation
   - Transaction management
   - Cross-cutting concerns (logging, caching)

3. **Codebase Layer** (`app/codebase/`)
   - Core domain operations
   - Database interactions
   - Complex query logic
   - Data transformation and validation

4. **Schema Layer** (`app/schemas/`)
   - Data validation models
   - Request/response serialization
   - Type safety with Pydantic

### Example Request Flow: Create Dashboard

```mermaid
graph TD
    A[POST /dashboards/create_dashboard] --> B[Router<br/>dashboard_routers.py]
    B --> C[Service<br/>DashboardService.create_dashboard]
    C --> D[Permission Check<br/>PermissionService]
    C --> E[Codebase<br/>CoreDashboard.create_dashboard]
    E --> F[Database<br/>Create Dashboard & Version]
    F --> G[Activity Logging]
    G --> H[Cache Invalidation]
    H --> I[HTTP Response]
```

### Code Organization Principles

- **Single Responsibility**: Each file handles a specific domain area
- **Dependency Inversion**: Services depend on abstractions, not implementations
- **Testability**: Clear separation allows for unit testing at each layer
- **Reusability**: Codebase methods can be reused across different services
- **Maintainability**: Changes are isolated to specific layers

### Key Design Patterns

1. **Repository Pattern**: Codebase layer abstracts database operations
2. **Service Layer Pattern**: Business logic encapsulation
3. **Factory Pattern**: Service instantiation and dependency injection
4. **Observer Pattern**: Event handling for activities and notifications

This architecture ensures scalability, maintainability, and clear separation between HTTP concerns, business logic, and data access.

## Configuration

### Database Configuration
The application uses PostgreSQL with asyncpg driver. Key configuration options:

```python
# app/core/config.py
DATABASE_URL: str  # Required: postgresql+asyncpg://...
DB_POOL_SIZE: int = 30
DB_MAX_OVERFLOW: int = 50
DB_POOL_TIMEOUT: int = 30
```

### Cache Configuration
Multiple caching backends supported:

```python
CACHE_BACKEND: str = "memory"  # Options: memory, redis, memcached
CACHE_TTL_DEFAULT: int = 300   # Default cache TTL in seconds
CACHE_ENDPOINT: str = "redis://localhost:6379"  # For Redis backend
```

### Observability Configuration
OpenTelemetry and Prometheus metrics:

```python
# Metrics are automatically enabled
LOG_LEVEL: str = "INFO"        # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT: str = "structured" # structured or json
```

### Authentication Configuration
The application uses JWT-based authentication via auth dependencies:

```python
# Authentication is handled via dependencies
from app.auth.dependencies import get_current_user

@router.get("/protected-endpoint")
async def protected_endpoint(current_user: dict = Depends(get_current_user)):
    # current_user contains: user_id, name, email, projects, workspaces
    return {"user": current_user["user_id"]}
```

## Development Guide

### Practical Examples

#### Working with the Dashboard Service
```python
from app.services.dashboard_service import DashboardService
from app.schemas.dashboards_schema import DashboardCreateSchema

# Create dashboard example
service = DashboardService()
dashboard_data = DashboardCreateSchema(
    name="Sales Dashboard",
    description="Monthly sales performance",
    project_id=uuid.uuid4(),
    content=[{"widget_id": "chart1", "type": "line", "data": {}}]
)

result = await service.create_dashboard(
    user_info={"id": user_id, "username": "john"},
    dashboard_data=dashboard_data
)
```

#### Debugging API Calls
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response
```

#### Testing Database Operations
```python
# Test database operations directly
from app.core.database import db_manager
from app.codebase.dashboards import CoreDashboard

async with db_manager.session() as session:
    dashboard = await CoreDashboard.get_dashboard_by_id(
        session=session, 
        dashboard_id=dashboard_uuid
    )
    print(f"Dashboard: {dashboard.name}")
```

### Adding New Routes

1. **Create schema** in `app/schemas/`
```python
# app/schemas/new_feature_schema.py
from pydantic import BaseModel

class NewFeatureCreateSchema(BaseModel):
    name: str
    description: str
```

2. **Create service** in `app/services/`
```python
# app/services/new_feature_service.py
from app.schemas.new_feature_schema import NewFeatureCreateSchema

class NewFeatureService:
    async def create_feature(self, user_info: dict, data: NewFeatureCreateSchema):
        # Business logic here
        pass
```

3. **Create router** in `app/routers/`
```python
# app/routers/new_feature_router.py
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.schemas.new_feature_schema import NewFeatureCreateSchema
from app.services.new_feature_service import NewFeatureService

router = APIRouter(prefix="/new-feature", tags=["new-feature"])
service = NewFeatureService()

@router.post("/create")
async def create_feature(
    data: NewFeatureCreateSchema,
    current_user: dict = Depends(get_current_user)
):
    return await service.create_feature(current_user, data)
```

4. **Register router** in `app/main.py`
```python
from app.routers.new_feature_router import router as new_feature_router
app.include_router(new_feature_router)
```

### Database Models

Database models are defined using SQLAlchemy ORM. Example model:

```python
# app/dbmodels/dashboard.py
from sqlalchemy import Column, String, UUID, DateTime, Text
from app.core.database import Base

class Dashboard(Base):
    __tablename__ = "dashboards"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Testing

Run tests with:
```bash
python -m pytest tests/
```

Write tests in `tests/` directory following the structure of the main application.

## Deployment

### Environment Setup

1. **Production database**: Use managed PostgreSQL service
2. **Caching**: Use Redis cluster for production
3. **Monitoring**: Configure OpenTelemetry collector
4. **Load balancing**: Use multiple application instances

### Docker Deployment

Create a `Dockerfile`:
```dockerfile
FROM python:3.14-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Checks

The application provides comprehensive health checks at `/health` endpoint:

```bash
curl http://localhost:8000/health
```

## Monitoring & Debugging

### Logging
Structured logging with request IDs:

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Operation completed", extra={"user_id": user_id, "dashboard_id": dashboard_id})
```

### Metrics
Available metrics endpoints:
- `/metrics` - Prometheus metrics
- `/health` - Application health
- OpenTelemetry traces via configured exporter

### Debug Mode
Enable debug mode for detailed error information:

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Verify DATABASE_URL format: `postgresql+asyncpg://...`
   - Check database server accessibility
   - Verify credentials

2. **n8n integration failures**
   - Check N8N_API_KEY validity
   - Verify n8n instance accessibility
   - Review workflow configuration

3. **Cache issues**
   - Verify Redis connection (if using Redis)
   - Check cache TTL settings
   - Monitor cache hit rates

### Performance Optimization

1. **Database tuning**
   - Adjust connection pool settings
   - Add database indexes for frequent queries
   - Use database connection pooling

2. **Caching strategy**
   - Cache frequently accessed data
   - Use appropriate TTL values
   - Implement cache warming

### Debugging Tips

#### Common Debugging Scenarios

1. **Database Connection Issues**
```python
# Check database connectivity
from app.core.database import db_manager
is_healthy = await db_manager.health_check()
print(f"Database health: {is_healthy}")
```

2. **Cache Issues**
```python
# Clear cache manually
from app.utils.cache import get_cache
cache = await get_cache()
await cache.clear()
```

3. **n8n Integration Debugging**
```python
# Test n8n connectivity
from app.services.n8n_service import N8NService
n8n_service = N8NService()
workflows = await n8n_service.get_workflows()
```

4. **Widget Locking Debugging**
```python
# Check active locks
from app.services.widget_locking_service import WidgetLockingService
locking_service = WidgetLockingService()
locks = await locking_service.get_active_sessions(dashboard_id)
```

#### Log Analysis
- Check `app/core/logging.py` for structured logging setup
- Look for request IDs in logs to track specific requests
- Enable DEBUG logging for detailed troubleshooting

## Issues & Enhancements Needed

### Current Issues

1. **Project ID Handling Enhancement**
   - **Issue**: `project_id` is hardcoded in n8n workflow creation with values like `"default"` and empty strings `""`
   - **File Locations**: 
     - `dashboard_workflow/app/services/features_service.py` lines 368-369: `project_id=str(user_info.get("project_id", "default"))`
     - `dashboard_workflow/app/services/features_service.py` lines 619-620: `project_id=""` (empty string)
     - `dashboard_workflow/app/n8n_samples/n8n_working_code.py` line 662: `project_id="cornerstone_learning"`
   - **Required Change**: Frontend code needs to add `project_id` into every widget and store that information in dashboard content
   - **Implementation**: Once the render API is fixed, modify the schedule creation flow to handle project_id per widget instead of hardcoded values
   - **Current Status**: Multiple hardcoded project_id values need to be replaced with dynamic per-widget project_id storage

2. **Database Configuration**
   - **Issue**: Using production database for development/testing
   - **Required Change**: Always configure the application to use local PostgreSQL instance instead of production database
   - **Implementation**: Update `DATABASE_URL` in `.env` file to point to local development database
   - **Importance**: Prevents accidental data modification in production environment

### Recommended Enhancements

1. **Code Quality Improvements**
   - Add comprehensive unit tests for all service layers
   - Implement integration tests for API endpoints
   - Add performance benchmarking for critical operations

2. **Security Enhancements**
   - Implement rate limiting for API endpoints
   - Add input validation for all user-provided data
   - Enhance authentication with refresh token mechanism

3. **Monitoring & Observability**
   - Add more detailed health checks
   - Implement structured logging across all services
   - Add performance metrics tracking

4. **Documentation Improvements**
   - Add API documentation with examples
   - Create deployment guides for different environments
   - Add troubleshooting guides for common issues

## Support

For issues and questions:
1. Check this documentation
2. Review application logs
3. Examine health endpoint responses
4. Contact development team

---

**Version**: 1.0.0  
**Last Updated**: $(date)
