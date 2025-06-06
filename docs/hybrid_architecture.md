# Hybrid Python + Go Job Scraping Architecture

## Overview

This hybrid architecture combines Python's rich ecosystem for orchestration and Go's performance for high-volume scraping. The system is designed for horizontal scaling and fault tolerance.

## Architecture Components

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                HYBRID ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐  │
│  │   FastAPI       │    │   Python Celery │    │      Go Scrapers           │  │
│  │   (API Layer)   │───▶│   (Orchestrator) │◄──▶│   (High Performance)       │  │
│  │                 │    │                 │    │   - Indeed Worker          │  │
│  │ - Job Tracking  │    │ - Job Scheduling│    │   - LinkedIn Worker        │  │
│  │ - Analytics API │    │ - Task Management│    │   - Glassdoor Worker       │  │
│  │ - Webhooks      │    │ - Error Handling │    │   - ZipRecruiter Worker    │  │
│  └─────────────────┘    │ - Data Processing│    │   - Google Jobs Worker     │  │
│           │              └─────────────────┘    │                             │  │
│           │                       │             │ Features:                   │  │
│           ▼                       ▼             │ - Anti-detection           │  │
│  ┌─────────────────┐    ┌─────────────────┐    │ - Proxy rotation           │  │
│  │   TimescaleDB   │    │   Redis Cluster │◄──▶│ - Rate limiting            │  │
│  │                 │    │                 │    │ - Concurrent requests      │  │
│  │ - Job Data      │    │ - Task Queue    │    │ - Browser automation       │  │
│  │ - Company Data  │    │ - Cache         │    │ - Stealth mode             │  │
│  │ - Analytics     │    │ - Pub/Sub       │    │                             │  │
│  │ - Time Series   │    │ - Sessions      │    └─────────────────────────────┘  │
│  └─────────────────┘    └─────────────────┘                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Communication Protocol

### Redis Message Channels

1. **Scraping Tasks** (`scraping:tasks`)
   - Python Celery → Go Scrapers
   - Task assignment and configuration

2. **Scraping Results** (`scraping:results`)
   - Go Scrapers → Python Celery
   - Job data and execution status

3. **Health Monitoring** (`scrapers:health`)
   - Bidirectional health checks
   - Performance metrics

4. **Error Reporting** (`scrapers:errors`)
   - Go Scrapers → Python Celery
   - Error details and retry requests

## Message Format

### Scraping Task Message
```json
{
  "task_id": "uuid",
  "scraper_type": "indeed|linkedin|glassdoor",
  "params": {
    "search_term": "software engineer",
    "location": "San Francisco, CA",
    "results_wanted": 50,
    "proxy": "user:pass@proxy:port",
    "user_agent": "Mozilla/5.0...",
    "delay_range": [1, 3]
  },
  "created_at": "2024-01-01T00:00:00Z",
  "timeout": 300,
  "retry_count": 0,
  "max_retries": 3
}
```

### Result Message
```json
{
  "task_id": "uuid",
  "status": "success|failed|partial",
  "scraper_type": "indeed",
  "execution_time": 45.2,
  "jobs_found": 47,
  "jobs_data": [
    {
      "title": "Software Engineer",
      "company": "Example Corp",
      "location": "San Francisco, CA",
      "salary_min": 120000,
      "salary_max": 180000,
      "job_url": "https://...",
      "description": "...",
      "posted_date": "2024-01-01",
      "job_hash": "sha256_hash"
    }
  ],
  "metadata": {
    "proxy_used": "proxy1:8080",
    "requests_made": 15,
    "rate_limited": false,
    "captcha_encountered": false
  },
  "completed_at": "2024-01-01T00:05:45Z",
  "error": null
}
```

## Component Responsibilities

### Python Orchestrator (Celery)
- **Task Scheduling**: Daily/hourly job scheduling
- **Job Management**: Create, queue, and track scraping tasks
- **Data Processing**: Process results from Go scrapers
- **Database Operations**: Store jobs, update metrics, analytics
- **Error Handling**: Retry logic, failure notifications
- **API Integration**: Serve results via FastAPI
- **Webhook Management**: Send notifications to subscribers

### Go Scrapers
- **High-Performance Scraping**: Concurrent HTTP requests
- **Anti-Detection**: User agent rotation, browser fingerprinting
- **Proxy Management**: Automatic proxy rotation and health checks
- **Rate Limiting**: Intelligent delays and backoff
- **Content Parsing**: Extract job data from HTML/JSON
- **Stealth Mode**: Avoid bot detection mechanisms
- **Health Monitoring**: Report performance metrics

## Scaling Strategy

### Horizontal Scaling
```yaml
# docker-compose.scale.yml
services:
  # Scale Go scrapers by type
  indeed-scraper:
    deploy:
      replicas: 3
  
  linkedin-scraper:
    deploy:
      replicas: 2
  
  # Scale Python workers
  python-orchestrator:
    deploy:
      replicas: 2
```

### Load Distribution
- **Geographic**: Different scrapers for different regions
- **Site-based**: Dedicated workers per job site
- **Time-based**: Peak hours vs off-hours scaling

## Deployment Strategy

### Development
```bash
# Start core services
docker-compose up -d timescaledb redis

# Start Python services
docker-compose up -d jobspy-api jobspy-scheduler

# Start Go scrapers
docker-compose up -d indeed-scraper linkedin-scraper
```

### Production
```bash
# Use docker swarm or kubernetes
docker stack deploy -c docker-compose.prod.yml jobspy
```

## Monitoring & Observability

### Metrics Collection
- **Scraping Performance**: Jobs/minute, success rate, response time
- **Resource Usage**: CPU, memory, network per scraper
- **Error Rates**: By scraper type and error category
- **Data Quality**: Duplicate detection, data completeness

### Health Checks
- **Redis Connectivity**: All components must maintain Redis connection
- **Database Health**: TimescaleDB query performance
- **Scraper Status**: Active workers, queue depth
- **API Performance**: Response times, error rates

## Anti-Detection Strategy

### Go Scrapers Features
1. **Rotating User Agents**: Large pool of real browser agents
2. **Proxy Rotation**: Automatic proxy switching and health monitoring
3. **Request Timing**: Human-like delays with jitter
4. **Browser Fingerprinting**: Consistent browser characteristics
5. **Session Management**: Maintain cookies and session state
6. **CAPTCHA Detection**: Identify and handle CAPTCHA challenges
7. **Rate Limiting**: Site-specific request limits

### Stealth Techniques
```go
// Example: Human-like browsing patterns
type BrowsingPattern struct {
    PageLoadDelay    time.Duration `json:"page_load_delay"`
    ScrollDelay      time.Duration `json:"scroll_delay"`
    ClickDelay       time.Duration `json:"click_delay"`
    TabSwitchDelay   time.Duration `json:"tab_switch_delay"`
}
```

## Fault Tolerance

### Python Layer
- **Celery Retry Logic**: Exponential backoff with jitter
- **Dead Letter Queue**: Failed tasks for manual review
- **Circuit Breaker**: Disable failing scrapers temporarily
- **Health Monitoring**: Automatic worker replacement

### Go Layer
- **Graceful Degradation**: Continue with available proxies
- **Connection Pooling**: Reuse HTTP connections efficiently
- **Timeout Handling**: Configurable timeouts per operation
- **Error Recovery**: Automatic retry with different strategies

## Performance Targets

### Go Scrapers
- **Throughput**: 1000+ jobs/minute per scraper instance
- **Concurrency**: 50-100 concurrent requests per scraper
- **Memory Usage**: <50MB per scraper instance
- **Response Time**: <2 seconds average per job page

### Overall System
- **Job Processing**: 10,000+ jobs/hour
- **Data Latency**: <5 minutes from scrape to database
- **Uptime**: 99.9% availability
- **Error Rate**: <1% failed scraping tasks

## Development Workflow

### Adding New Scrapers
1. Create Go scraper module
2. Implement standard interface
3. Add Redis communication
4. Update Python orchestrator
5. Add configuration
6. Write tests
7. Deploy and monitor

### Testing Strategy
- **Unit Tests**: Each scraper component
- **Integration Tests**: Redis communication
- **End-to-End Tests**: Full scraping workflow
- **Load Tests**: Performance under scale
- **Anti-Detection Tests**: Stealth capabilities