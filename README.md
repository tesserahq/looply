<p align="center">
  <img width="140px" src="assets/logo.png">
  
  <h2 align="center">Looply</h2>
  <p align="center">
    A comprehensive contact management and waitlist system built with FastAPI and PostgreSQL
  </p>
</p>

---

## Overview

**Looply** is a modern, production-ready API service for managing contacts, organizing them into lists, and handling waitlist workflows. It provides a robust foundation for contact management applications with features like full-text search, status tracking, and multi-list organization.

## Features

### 📇 Contact Management

- **Comprehensive contact profiles**: Store detailed contact information including names, company, job title, phone, email, address, and notes
- **Full-text search**: PostgreSQL-powered full-text search across all contact fields with weighted relevance
- **Duplicate prevention**: Automatic detection and prevention of duplicate emails and phone numbers
- **Contact types**: Organize contacts by type (personal, business, etc.)
- **Active/inactive status**: Enable or disable contacts as needed

### 📋 Contact Lists

- **Create and manage lists**: Organize contacts into custom lists with names and descriptions
- **Member management**: Add, remove, and query contacts in lists
- **Bidirectional relationships**: Find all lists a contact belongs to
- **Member counting**: Quickly retrieve member counts for any list

### ⏳ Waiting Lists

- **Advanced status tracking**: Manage waiting list members with comprehensive status workflow:
  - `pending` - Awaiting approval or notification
  - `approved` - Approved for the waitlist
  - `rejected` - Rejected from the waitlist
  - `notified` - Member has been notified
  - `accepted` - Member accepted their spot
  - `declined` - Member declined their spot
  - `active` - Currently active
  - `inactive` - Currently inactive
  - `cancelled` - Cancelled participation
- **Status queries**: Filter members by status and get counts by status
- **Bulk operations**: Update multiple members' status simultaneously
- **Member history**: Track when members joined and status changes

### 👤 User Management

- **User profiles**: Manage user accounts with email, username, and profile information
- **Authentication**: Integrated with Tessera SDK for authentication and authorization
- **Multi-tenant support**: Each resource is scoped to the creating user

## Technology Stack

- **Framework**: FastAPI (async Python web framework)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Tessera SDK (JWT-based authentication)
- **Pagination**: fastapi-pagination for efficient list endpoints
- **Validation**: Pydantic for data validation
- **Migrations**: Alembic for database migrations
- **Observability**:
  - Rollbar for error tracking
  - OpenTelemetry for distributed tracing
- **Background Jobs**: Celery for asynchronous task processing
- **Cache**: Redis for caching and background job queues
- **Email**: Postmarker for email delivery

## Architecture

The service follows a clean architecture pattern:

```text
app/
├── models/          # SQLAlchemy models
├── schemas/         # Pydantic schemas for validation
├── services/        # Business logic layer
├── routers/         # API endpoints
├── middleware/      # Authentication and session management
├── exceptions/      # Exception handlers
├── core/            # Core configuration and logging
└── utils/           # Utility functions
```

## API Endpoints

### Contacts

- `POST /contacts` - Create a new contact
- `GET /contacts` - List all contacts (paginated)
- `GET /contacts/{id}` - Get contact details
- `PUT /contacts/{id}` - Update a contact
- `DELETE /contacts/{id}` - Delete a contact

### Contact Lists

- `POST /contact-lists` - Create a new contact list
- `GET /contact-lists` - List all contact lists (paginated)
- `GET /contact-lists/{id}` - Get contact list details
- `PUT /contact-lists/{id}` - Update a contact list
- `DELETE /contact-lists/{id}` - Delete a contact list
- `POST /contact-lists/{id}/members` - Add members to a list
- `DELETE /contact-lists/{id}/members/{contact_id}` - Remove a member
- `GET /contact-lists/{id}/members` - Get all members of a list
- `GET /contact-lists/{id}/members/count` - Get member count
- `GET /contacts/{contact_id}/contact-lists` - Get all lists a contact belongs to

### Waiting Lists

- `POST /waiting-lists` - Create a new waiting list
- `GET /waiting-lists` - List all waiting lists (paginated)
- `GET /waiting-lists/{id}` - Get waiting list details
- `PUT /waiting-lists/{id}` - Update a waiting list
- `DELETE /waiting-lists/{id}` - Delete a waiting list
- `GET /waiting-lists/member-statuses` - List all available statuses
- `POST /waiting-lists/{id}/members` - Add members with status
- `PUT /waiting-lists/{id}/members/{contact_id}/status` - Update member status
- `PUT /waiting-lists/{id}/members/bulk-status` - Bulk update member statuses
- `GET /waiting-lists/{id}/members/by-status/{status}` - Get members by status
- `GET /waiting-lists/{id}/members/by-status/{status}/count` - Get count by status
- `GET /waiting-lists/{id}/members/{contact_id}/status` - Get a member's status
- `GET /waiting-lists/{id}/members/{contact_id}/is-member` - Check membership

### Users

- `POST /users` - Create a new user
- `GET /users` - List all users
- `GET /users/{id}` - Get user details
- `PUT /users/{id}` - Update a user
- `DELETE /users/{id}` - Delete a user
- `POST /users/{id}/verify` - Verify a user

## Key Features

### Full-Text Search
Contacts include a PostgreSQL `tsvector` column that automatically indexes all text fields (names, company, email, phone, address, notes) with weighted relevance for fast searching.

### Soft Deletes
All resources support soft deletion - items are marked as deleted but remain in the database for audit purposes.

### Pagination
List endpoints use `fastapi-pagination` to provide consistent, efficient pagination across all resources.

### Multi-Tenancy
Resources are automatically scoped to the authenticated user who created them, ensuring data isolation.

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Redis (for caching and background jobs)
- Poetry (for dependency management)

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd looply
```

2. Install dependencies:

```bash
poetry install
```

3. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run database migrations:

```bash
alembic upgrade head
```

5. Start the development server:

```bash
poetry run python run.py
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

## Configuration

Key environment variables:

- `DATABASE_URL` - PostgreSQL connection string
- `IDENTIES_HOST` - Tessera authentication service URL
- `REDIS_HOST` - Redis host
- `REDIS_PORT` - Redis port
- `ENVIRONMENT` - Environment (development/production)
- `DISABLE_AUTH` - Disable authentication for testing (development only)
- `ROLLBAR_ACCESS_TOKEN` - Rollbar error tracking token
- `OTEL_ENABLED` - Enable OpenTelemetry tracing
- `LOG_LEVEL` - Logging level (INFO, DEBUG, etc.)

## Testing

Run tests with pytest:

```bash
poetry run pytest
```

## Development

The project follows PEP 8 style guidelines and uses:

- `black` for code formatting
- `ruff` for linting
- Type hints throughout

## License

See LICENSE file for details.
