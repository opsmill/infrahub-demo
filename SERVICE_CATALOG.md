# Infrahub Service Catalog

## Overview

The Infrahub Service Catalog is a Streamlit-based web application that provides a user-friendly interface for viewing and creating data center infrastructure in Infrahub. It runs as an optional Docker container alongside Infrahub services.

## Features

- **Landing Page**: View lists of Data Centers and Colocation Centers with branch selection
- **Create DC Page**: Form-based interface for creating new Data Centers with automatic branch creation and Proposed Change generation
- **Branch Management**: Switch between Infrahub branches to view infrastructure in different contexts
- **Workflow Automation**: Automatically creates branches, loads data, waits for generators, and creates Proposed Changes

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Running Infrahub instance
- Network connectivity between containers

## Setup

### 1. Configuration

The service catalog can be configured via environment variables or `docker-compose.override.yml`.

#### Environment Variables

Copy the `.env.example` file to `.env` and update the values as needed:

```bash
cp .env.example .env
```

The `.env` file is gitignored and will not be committed to version control. See the `.env.example` file for detailed documentation of all available variables.

#### Docker Compose Configuration

The service catalog is configured via `docker-compose.override.yml`. Since this file is in `.gitignore`, you'll need to create or modify it locally.

The service catalog service is already defined in the repository's `docker-compose.override.yml` with the following configuration:

```yaml
services:
  streamlit-service-catalog:
    build:
      context: .
      dockerfile: service_catalog/Dockerfile
    container_name: infrahub-service-catalog
    ports:
      - "8501:8501"
    environment:
      - INFRAHUB_ADDRESS=http://infrahub-server:8000
      - DEFAULT_BRANCH=main
      - GENERATOR_WAIT_TIME=60
    volumes:
      - ./service_catalog:/app
      - ./objects:/objects:ro
      - ./docs/static/img:/app/assets:ro
    depends_on:
      - infrahub-server
    profiles:
      - service-catalog
    networks:
      - infrahub
```

### 2. Environment Variables

The following environment variables can be configured:

| Variable | Default | Description |
|----------|---------|-------------|
| `INFRAHUB_ADDRESS` | `http://infrahub-server:8000` | URL to the Infrahub API server |
| `DEFAULT_BRANCH` | `main` | Default branch to select on startup |
| `GENERATOR_WAIT_TIME` | `60` | Seconds to wait for generator completion after DC creation |
| `STREAMLIT_PORT` | `8501` | Port for the Streamlit application |
| `API_TIMEOUT` | `30` | Timeout in seconds for API requests |
| `API_RETRY_COUNT` | `3` | Number of retries for failed API requests |

You can override these in the `docker-compose.override.yml` file under the `environment` section.

## Usage

### Starting the Service Catalog

The service catalog uses Docker Compose profiles for conditional startup. This allows you to enable or disable it as needed.

#### Start Infrahub WITH Service Catalog

```bash
docker-compose --profile service-catalog up
```

Or with detached mode:

```bash
docker-compose --profile service-catalog up -d
```

#### Start Infrahub WITHOUT Service Catalog

```bash
docker-compose up
```

Or with detached mode:

```bash
docker-compose up -d
```

### Accessing the Application

Once started, the service catalog is accessible at:

```
http://localhost:8501
```

### Stopping the Service Catalog

To stop all services including the service catalog:

```bash
docker-compose --profile service-catalog down
```

To stop only the service catalog while keeping Infrahub running:

```bash
docker-compose stop streamlit-service-catalog
```

## Application Features

### Landing Page

The landing page displays:

- **Infrahub Logo**: Automatically switches between light and dark mode versions
- **Branch Selector**: Dropdown menu to switch between Infrahub branches
- **Data Centers List**: Table showing all TopologyDataCenter objects in the selected branch
- **Colocation Centers List**: Table showing all TopologyColocationCenter objects in the selected branch

### Create Data Center Page

Navigate to the "Create Data Center" page from the sidebar to:

1. Fill in DC details using a form with pre-populated dropdown options
2. Submit the form to trigger the automated workflow:
   - Creates a new branch (named `add-{dc_name}`)
   - Loads the DC data to the new branch
   - Waits for the Infrahub generator to complete (60 seconds by default)
   - Creates a Proposed Change for review
3. View the Proposed Change URL to review and merge changes in Infrahub

### Form Fields

The DC creation form includes:

- **Required Fields**:
  - Name
  - Location
  - Description
  - Strategy (dropdown)
  - Design (dropdown)
  - Provider (dropdown)

- **Optional Fields**:
  - Emulation (checkbox)

- **Subnet Configuration**:
  - Management Subnet (prefix, status, role)
  - Customer Subnet (prefix, status, role)
  - Technical Subnet (prefix, status, role)

## Troubleshooting

### Container Won't Start

1. Check that Infrahub is running:
   ```bash
   docker-compose ps
   ```

2. Check container logs:
   ```bash
   docker-compose logs streamlit-service-catalog
   ```

3. Verify the Dockerfile exists:
   ```bash
   ls -la service_catalog/Dockerfile
   ```

### Cannot Connect to Infrahub

1. Verify the `INFRAHUB_ADDRESS` environment variable is correct
2. Check that the service catalog container is on the same network as Infrahub
3. Test connectivity from within the container:
   ```bash
   docker-compose exec streamlit-service-catalog curl http://infrahub-server:8000
   ```

### Application Shows Errors

1. Check the Streamlit logs:
   ```bash
   docker-compose logs -f streamlit-service-catalog
   ```

2. Verify all required volumes are mounted correctly:
   ```bash
   docker-compose exec streamlit-service-catalog ls -la /app
   docker-compose exec streamlit-service-catalog ls -la /objects
   docker-compose exec streamlit-service-catalog ls -la /app/assets
   ```

### DC Creation Fails

1. Verify the branch was created in Infrahub
2. Check if the generator completed successfully
3. Review the error message displayed in the Streamlit UI
4. Check Infrahub logs for generator errors

## Development

### Local Development Without Docker

For local development, you can run the Streamlit app directly:

1. Install dependencies:
   ```bash
   cd service_catalog
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export INFRAHUB_ADDRESS=http://localhost:8000
   export DEFAULT_BRANCH=main
   ```

3. Run the application:
   ```bash
   streamlit run app.py
   ```

### Rebuilding the Container

After making changes to the code or Dockerfile:

```bash
docker-compose --profile service-catalog build streamlit-service-catalog
docker-compose --profile service-catalog up -d
```

### Viewing Logs

To view real-time logs:

```bash
docker-compose logs -f streamlit-service-catalog
```

## Architecture

The service catalog consists of:

- **app.py**: Main landing page
- **pages/1_Create_DC.py**: DC creation page
- **utils/api.py**: Infrahub API client with retry logic
- **utils/config.py**: Configuration management
- **utils/ui.py**: Shared UI components and helpers

The application communicates with Infrahub via:
- REST API endpoints for listing objects
- GraphQL API for mutations (branch creation, DC creation, Proposed Change creation)

## Security Considerations

- The service catalog runs in the same Docker network as Infrahub
- Template files are mounted read-only
- All configuration is via environment variables
- Currently assumes no authentication (future enhancement)

## Future Enhancements

- API token authentication support
- Bulk DC creation
- DC editing and deletion
- Advanced filtering and search
- Export functionality (CSV/JSON)
- Real-time updates via WebSocket
- Validation preview before creating Proposed Changes
- Template management UI
- Audit log of changes

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review container logs
3. Verify Infrahub is running correctly
4. Check the Infrahub documentation for API-related issues
