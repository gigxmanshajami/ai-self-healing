# System Design Document

## Overview

The AI Self-Healing Web Scraper is a production-ready system that combines traditional web scraping with machine learning to automatically recover from selector failures.

## High-Level Architecture

### Components

| Component | Responsibility |
|-----------|----------------|
| **Selenium Driver** | Browser automation, page rendering, screenshot capture |
| **Base Scraper** | DOM parsing, element extraction, similarity scoring |
| **Failure Detector** | Identifies failure types and triggers healing |
| **Feature Extractor** | Converts DOM elements to ML feature vectors |
| **Selector Model** | ML prediction for candidate element ranking |
| **XPath Generator** | Creates multiple XPath strategies for robustness |
| **Self-Healing Engine** | Orchestrates the 8-step healing pipeline |
| **Storage Layer** | Persists selectors, logs, training data in SQLite |
| **API Layer** | REST endpoints for frontend integration |

## Data Flow

```
Request → API → Scraper → [Success] → Response
                   ↓
              [Failure]
                   ↓
         Failure Detector
                   ↓
         Self-Healing Engine
                   ↓
    ┌──────────────────────────┐
    │  Feature Extraction      │
    │  ML Prediction           │
    │  XPath Generation        │
    │  Candidate Validation    │
    └──────────────────────────┘
                   ↓
         New Selector → Storage → Response
```

## Database Schema

### Tables

**selector_history**
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| url | TEXT | Target URL |
| original_selector | TEXT | Failed selector |
| new_selector | TEXT | Healed selector |
| confidence | REAL | ML confidence score |
| strategy | TEXT | XPath strategy used |
| status | TEXT | SUCCESS/FAILED |
| created_at | TIMESTAMP | When healing occurred |

**healing_logs**
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| job_id | TEXT | Reference to scrape job |
| level | TEXT | INFO/WARNING/ERROR |
| message | TEXT | Log message |
| metadata | JSON | Additional context |
| created_at | TIMESTAMP | Log timestamp |

**training_data**
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| features | BLOB | Serialized feature vector |
| label | INTEGER | 1 = match, 0 = no match |
| url | TEXT | Source URL |
| created_at | TIMESTAMP | Collection timestamp |

## API Design

### Endpoints

#### POST /api/v1/scrape
Executes a scrape job with optional self-healing.

Request:
```json
{
  "url": "https://example.com",
  "selectors": {"title": ".product-name"},
  "enable_healing": true,
  "timeout": 15
}
```

Response:
```json
{
  "job_id": "uuid",
  "status": "success",
  "results": [...],
  "healing_triggered": true,
  "total_healed": 1
}
```

#### POST /api/v1/heal
Manually trigger healing for a specific selector.

#### GET /api/v1/logs
Paginated healing logs with filtering.

#### GET /api/v1/models/status
ML model metrics and healing statistics.

#### GET /api/v1/selectors/history
Historical selector changes for analysis.

## Error Handling

| Error Type | Handling |
|------------|----------|
| Element Not Found | Trigger healing |
| Stale Element | Trigger healing after retry |
| Timeout | Increase wait, then heal |
| Empty Result | Validate content, may heal |
| Network Error | Retry with backoff |
| Low Confidence | Log warning, use selector |

## Performance Considerations

1. **Async Operations**: FastAPI + aiosqlite for non-blocking I/O
2. **Model Caching**: Load model once at startup
3. **Connection Pooling**: Reuse database connections
4. **Background Tasks**: Heavy processing in background
5. **Lazy Loading**: Components loaded on-demand

## Scalability

Current design supports single-instance deployment. For scaling:

- **Horizontal**: Add load balancer + multiple backend instances
- **Database**: Migrate to PostgreSQL for concurrent writes
- **Caching**: Add Redis for model predictions
- **Queue**: Use Celery/RQ for async job processing

## Security

- CORS configured for known frontends
- Input validation via Pydantic
- SQL parameterization (no injection)
- Rate limiting (recommended for production)
- Authentication (not implemented, add JWT/API keys)
