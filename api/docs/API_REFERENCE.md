# Deep Search API Reference

## Overview

The Deep Search API provides endpoints for automated academic research. This document covers authentication, endpoints, and error handling.

## Base URL

```
Production: https://api.deep-search.example.com
Development: http://localhost:8000
```

## Authentication

The API supports multiple authentication methods:

### 1. JWT Bearer Token

```http
Authorization: Bearer <token>
```

JWT tokens should be obtained from your identity provider. Configure the API to validate tokens using:
- `JWT_SECRET_KEY` - For HS256 algorithm
- `JWT_JWKS_URL` - For RS256 with JWKS

### 2. API Key

```http
X-API-Key: sk_your_api_key_here
```

API keys can be configured via environment variables:
```bash
API_KEY_MYAPP=sk_abc123:user_id:365  # Format: key:user_id:expiry_days
```

### 3. Demo Mode (Development Only)

Set `AUTH_DEMO_MODE=true` for development without authentication.

---

## Endpoints

### Health

#### GET /
Returns API information.

**Response:**
```json
{
  "message": "Deep Research API",
  "version": "0.1.0",
  "status": "running",
  "docs": "/docs",
  "health": "/health"
}
```

#### GET /health
Health check endpoint.

**Response:**
```json
{"ok": true}
```

---

### Projects

#### POST /projects
Create a new research project.

**Request Body:**
```json
{
  "title": "Effects of climate change on marine ecosystems",
  "goal": "Investigate the impact of rising sea temperatures on coral reefs",
  "maxParagraphs": 6
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | Yes | Research topic (3-500 chars) |
| goal | string | No | Detailed research goal (0-2000 chars) |
| maxParagraphs | integer | No | Max sections in report (1-20, default: 6) |

**Response:**
```json
{
  "project_id": "507f1f77bcf86cd799439011"
}
```

**Rate Limit:** 20 requests per minute

---

### Runs

#### POST /runs
Create a new research run with automatic routing.

**Request Body:**
```json
{
  "projectId": "507f1f77bcf86cd799439011",
  "config": {
    "deepMode": true,
    "minCitations": 5,
    "maxParagraphs": 6,
    "searchProvider": "hybrid"
  },
  "idempotencyKey": "unique-request-id-12345678"
}
```

**Config Options:**
| Field | Type | Description |
|-------|------|-------------|
| forceMode | string | Override routing: "simple" or "agentic" |
| deepMode | boolean | Request thorough research |
| minCitations | integer | Minimum sources required (0-100) |
| requireRecent | boolean | Prioritize recent papers |
| maxParagraphs | integer | Report length (1-20) |
| searchProvider | string | "hybrid", "academic", "web" |
| academicOnly | boolean | Only use academic sources |
| language | string | Result language (en, es, fr, de, etc.) |

**Response:**
```json
{
  "run_id": "507f1f77bcf86cd799439012",
  "mode": "agentic",
  "routing": {
    "mode": "agentic",
    "score": 0.75,
    "threshold": 0.5,
    "factors": {
      "topicLength": 45,
      "detectedDomains": ["climate", "marine biology"],
      "deepMode": true,
      "minCitations": 5,
      "requireRecent": false
    },
    "reasoning": "Complex topic with multiple domains detected"
  }
}
```

**Idempotency:**
Include an `idempotencyKey` (16-64 alphanumeric chars) to prevent duplicate runs on retry. The same key returns the same response for 24 hours.

**Rate Limit:** 10 requests per minute

---

#### GET /runs/{run_id}/status
Get run progress and status.

**Response:**
```json
{
  "status": "running",
  "progress": 45,
  "currentStep": "Researching section 3",
  "mode": "agentic"
}
```

---

#### DELETE /runs/{run_id}
Delete a run and all associated data.

**Response:**
```json
{
  "status": "deleted",
  "run_id": "507f1f77bcf86cd799439012"
}
```

---

#### POST /runs/{run_id}/cancel
Cancel an in-progress run.

**Response:**
```json
{
  "status": "cancelled",
  "run_id": "507f1f77bcf86cd799439012"
}
```

---

#### GET /runs/{run_id}/report
Get the generated research report.

**Response:**
```json
{
  "markdown": "# Research Report\n\n## Introduction\n...",
  "citations": {...},
  "generatedAt": "2024-01-15T10:30:00Z"
}
```

---

### Streaming

#### GET /runs/{run_id}/events/stream
Server-Sent Events stream of research progress.

**Response (SSE):**
```
data: {"type": "progress", "step": "searching", "message": "Searching academic sources..."}

data: {"type": "source_found", "title": "Climate Change Effects", "url": "..."}

data: {"done": true, "status": "done"}
```

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": true,
  "code": "VAL_2001",
  "message": "Validation error: topic too short",
  "details": {
    "field": "title",
    "received": "ab",
    "minimum": 3
  },
  "request_id": "req_abc123"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| **Authentication (1xxx)** |
| AUTH_1001 | Authentication required |
| AUTH_1002 | Token expired |
| AUTH_1003 | Token invalid |
| AUTH_1004 | Insufficient permissions |
| AUTH_1005 | API key invalid |
| AUTH_1006 | API key expired |
| **Validation (2xxx)** |
| VAL_2001 | Validation error |
| VAL_2002 | Invalid project ID |
| VAL_2003 | Invalid run ID |
| VAL_2004 | Invalid configuration |
| VAL_2005 | Input too long |
| VAL_2006 | Invalid URL |
| **Resources (3xxx)** |
| RES_3001 | Resource not found |
| RES_3002 | Project not found |
| RES_3003 | Run not found |
| RES_3004 | Already exists |
| RES_3005 | Conflict |
| **Rate Limiting (4xxx)** |
| RATE_4001 | Rate limit exceeded |
| RATE_4002 | Quota exceeded |
| **External Services (5xxx)** |
| EXT_5001 | LLM service unavailable |
| EXT_5002 | LLM rate limited |
| EXT_5003 | Search service unavailable |
| EXT_5004 | Database error |
| **Internal (6xxx)** |
| INT_6001 | Internal error |
| INT_6002 | Service degraded |

---

## Rate Limiting

Rate limits are applied per-user or per-API-key:

| Endpoint | Limit |
|----------|-------|
| POST /projects | 20/min |
| POST /runs | 10/min |
| GET /s3/presign | 30/min |
| Default | 60/min |

When rate limited, you'll receive:

```json
{
  "error": true,
  "code": "RATE_4001",
  "message": "Rate limit exceeded. Maximum 10 requests per 60 seconds.",
  "details": {
    "retry_after": 45
  }
}
```

**Headers:**
```http
Retry-After: 45
```

---

## Best Practices

### 1. Use Idempotency Keys
Always include an idempotency key for run creation to handle network retries safely.

```python
import uuid
idempotency_key = str(uuid.uuid4())
```

### 2. Handle Rate Limits
Implement exponential backoff when you receive 429 responses:

```python
async def create_run_with_retry(data, max_retries=3):
    for attempt in range(max_retries):
        response = await client.post("/runs", json=data)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            await asyncio.sleep(retry_after * (2 ** attempt))
            continue
        return response
    raise Exception("Max retries exceeded")
```

### 3. Stream Results
Use SSE streaming for real-time progress updates instead of polling.

### 4. Validate Inputs
The API validates inputs strictly. Ensure:
- Topics are 3-500 characters
- Goals are under 2000 characters
- Config values are within valid ranges

---

## Changelog

### v0.1.0
- Initial API release
- JWT and API key authentication
- Rate limiting
- Idempotency keys
- Structured error responses
- Input validation and sanitization
