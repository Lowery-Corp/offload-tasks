# offload-tasks

A FastAPI application with Celery for offloading long-running tasks to background workers. This stack demonstrates asynchronous task processing using Redis as a message broker and result backend.

## Architecture

- **FastAPI**: Web API framework for handling HTTP requests
- **Celery**: Distributed task queue for background job processing
- **Redis**: Message broker and result backend
- **Flower**: Web-based tool for monitoring Celery clusters

## Features

- Asynchronous document processing tasks
- Task status tracking and monitoring
- Dockerized deployment with Docker Compose
- Health checks for service dependencies
- Flower monitoring dashboard

## Quick Start

### Prerequisites

- Docker
- Docker Compose

### Running the Stack

1. Clone the repository and navigate to the project directory:
```bash
cd offload-tasks
```

2. Start all services:
```bash
docker-compose up -d
```

3. The services will be available at:
   - **API**: http://localhost:8001
   - **Flower Dashboard**: http://localhost:5555
   - **Redis**: localhost:6380

### API Usage

#### Queue a Document Processing Task

```bash
curl -X POST "http://localhost:8001/documents/123/process"
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

## Services

### API Service
- **Port**: 8001 (mapped to container port 8000)
- **Purpose**: Handles HTTP requests and queues tasks
- **Endpoints**:
  - `POST /documents/{document_id}/process` - Queue document processing

### Worker Service
- **Purpose**: Processes background tasks from the Redis queue
- **Tasks**: Document processing (simulates 10-second processing time)

### Flower Service
- **Port**: 5555
- **Purpose**: Monitor Celery workers and tasks
- **Features**: Real-time task monitoring, worker statistics

### Redis Service
- **Port**: 6380 (mapped to container port 6379)
- **Purpose**: Message broker (database 0) and result backend (database 1)
- **Configuration**: Persistence disabled for development

## Development

### Local Development Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export CELERY_BROKER_URL="redis://localhost:6380/0"
export CELERY_RESULT_BACKEND="redis://localhost:6380/1"
```

3. Start Redis:
```bash
docker run -p 6380:6379 redis:latest
```

4. Start the API server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Start a Celery worker:
```bash
celery -A app.worker.celery_app worker --loglevel=info
```

6. (Optional) Start Flower:
```bash
celery -A app.worker.celery_app flower --port=5555
```

### Project Structure

```
offload-tasks/
├── app/
│   ├── main.py              # FastAPI application
│   ├── worker.py            # Celery configuration
│   └── tasks/
│       └── file_tasks.py    # Task definitions
├── docker-compose.yaml      # Service orchestration
├── Dockerfile              # Container image definition
├── requirements.txt        # Python dependencies
└── README.md
```

## Configuration

### Environment Variables

- `CELERY_BROKER_URL`: Redis URL for message broker
- `CELERY_RESULT_BACKEND`: Redis URL for storing task results
- `REDIS_URL`: Base Redis connection URL

### Celery Configuration

- **Serializer**: JSON
- **Timezone**: UTC
- **Task Tracking**: Enabled

## Monitoring

Access the Flower dashboard at http://localhost:5555 to:
- Monitor active workers
- View task history and status
- Check queue lengths
- Analyze task performance

## Scaling

To scale workers horizontally:

```bash
docker-compose up --scale worker=3
```

This will start 3 worker instances to process tasks in parallel.

## Troubleshooting

### Common Issues

1. **Services not starting**: Check if ports 8001, 5555, or 6380 are already in use
2. **Task failures**: Check worker logs with `docker-compose logs worker`
3. **Connection errors**: Ensure Redis is healthy with `docker-compose ps`

### Logs

View service logs:
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs api
docker-compose logs worker
docker-compose logs flower
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request