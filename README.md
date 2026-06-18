# RateMaster

A distributed rate limiter service built with FastAPI and Redis, implementing three industry-standard algorithms with atomic Lua scripts. Deployable as FastAPI middleware or as a Kong API Gateway plugin.

## Architecture

```
                         ┌──────────────┐
                         │  Kong Plugin  │  (Lua, gateway layer)
                         │  Token Bucket │
                         └──────┬───────┘
                                │
Client ──► FastAPI Middleware ───┼──► Algorithm Router ──► Redis (Lua script)
                                │        │
                                │   ┌────┴────────────────┐
                                │   │  Fixed Window        │
                                │   │  Token Bucket        │
                                │   │  Sliding Window Log  │
                                │   └─────────────────────┘
                                │
                         ┌──────┴───────┐
                         │  Prometheus   │──► Grafana Dashboard
                         │  /metrics     │
                         └──────────────┘
```

## Quick Start

```bash
# Start all services (Redis, FastAPI, Prometheus, Grafana)
docker-compose up --build

# Test each algorithm
curl http://localhost:8000/api/status    # Fixed Window (100 req/min)
curl http://localhost:8000/api/search    # Token Bucket (20 req/min)
curl -X POST http://localhost:8000/api/login  # Sliding Window (5 req/min)

# Check rate limit headers
curl -v http://localhost:8000/api/search

# View metrics
curl http://localhost:8000/metrics/

# Grafana dashboard
open http://localhost:3000  # admin / admin
```

## Algorithm Comparison

| Algorithm | Time Complexity | Memory | Burst Handling | Best For |
|---|---|---|---|---|
| **Fixed Window** | O(1) | O(1) per key | Boundary burst weakness | Simple rate limiting, high throughput |
| **Token Bucket** | O(1) | O(1) per key | Smooth, configurable burst | API rate limiting, bursty traffic |
| **Sliding Window Log** | O(1) amortized | O(n) per window | No boundary issues | Strict rate limiting, login/auth |

### How Each Algorithm Works

**Fixed Window Counter** — Divides time into fixed windows (e.g., 0:00-1:00, 1:00-2:00). Increments a counter per window. Simple and fast, but a client can send 2x the limit across a window boundary.

**Token Bucket** — A bucket fills with tokens at a steady rate. Each request consumes one token. If the bucket is empty, the request is denied. Allows controlled bursts up to bucket capacity.

**Sliding Window Log** — Stores a timestamp for every request in a sorted set. On each new request, it removes expired entries and counts the rest. Most precise, but uses more memory.

## Load Test Results

**Configuration:** 50 concurrent users, 60 second duration, 10 users/sec ramp-up

| Endpoint | Algorithm | Limit | Total Requests | Denied | Deny Rate | Avg Latency |
|---|---|---|---|---|---|---|
| `/api/search` | Token Bucket | 20/min | 5,700 | 5,660 | 99.4% | 4ms |
| `/api/status` | Fixed Window | 100/min | 1,600 | 1,500 | 93.8% | 5ms |
| `/api/login` | Sliding Window | 5/min | 800 | 795 | 99.4% | 5ms |

Key observations:
- All three algorithms maintain **sub-5ms latency** under heavy concurrent load
- `/api/login` (5 req/min limit) reaches 99%+ denial rate almost immediately
- `/api/status` (100 req/min limit) has the lowest denial rate due to its generous limit
- Zero 5xx errors — the rate limiter is stable under pressure

```bash
# Reproduce load test results
pip install locust
locust -f scripts/load_test.py --headless -u 50 -r 10 -t 60s --host http://localhost:8000
```

## API Reference

### Endpoints

| Method | Path | Algorithm | Rate Limit |
|---|---|---|---|
| GET | `/api/status` | Fixed Window | 100 req/min |
| GET | `/api/search` | Token Bucket | 20 req/min |
| POST | `/api/login` | Sliding Window | 5 req/min |
| GET | `/health` | — | No limit |
| GET | `/metrics/` | — | No limit |

### Response Headers

Every rate-limited response includes:

```
X-RateLimit-Limit: 20          # Max requests allowed in window
X-RateLimit-Remaining: 15      # Requests remaining
X-RateLimit-Reset: 1718742000  # Unix timestamp when the limit resets
```

When rate limited (HTTP 429):

```json
{
  "error": "rate_limit_exceeded",
  "retry_after": 3
}
```

```
Retry-After: 3
X-RateLimit-Remaining: 0
```

## Kong Plugin

The same token bucket algorithm is implemented as a Kong API Gateway plugin in Lua, enabling rate limiting at the gateway layer before requests reach the backend.

### Installation

```bash
# Copy plugin to Kong's plugin directory
cp -r kong-plugin/ /path/to/kong/plugins/ratemaster/

# Add to Kong's configuration (kong.conf)
plugins = bundled,ratemaster

# Enable on a route via Kong Admin API
curl -X POST http://localhost:8001/routes/{route_id}/plugins \
  --data "name=ratemaster" \
  --data "config.limit_per_second=10" \
  --data "config.burst_capacity=20" \
  --data "config.redis_host=redis" \
  --data "config.redis_port=6379"
```

### Plugin Configuration

| Field | Type | Default | Description |
|---|---|---|---|
| `limit_per_second` | number | required | Steady-state token refill rate |
| `burst_capacity` | number | required | Maximum tokens (burst size) |
| `redis_host` | string | `"redis"` | Redis hostname |
| `redis_port` | number | `6379` | Redis port |
| `identifier_header` | string | `"X-API-Key"` | Header for client identification |

## Design Decisions

**Why Lua scripts in Redis?** Each algorithm's read-check-write runs as a single atomic Redis operation. Redis is single-threaded, so Lua scripts execute without interruption — no race conditions, no distributed locks needed. This also reduces network round-trips from 2-3 (GET → check → SET) to 1 (EVALSHA).

**Why three algorithms?** Different endpoints have different needs. Login pages need strict per-second limiting (sliding window). Search APIs need burst tolerance (token bucket). Status pages just need a simple ceiling (fixed window). Per-route algorithm selection lets you match the right tool to the job.

**Why fail-open on Redis errors?** If Redis goes down, the rate limiter should not block all traffic. Briefly allowing excess requests is better than a total outage. The middleware and Kong plugin both log a warning and let the request through when Redis is unreachable.

**Why EVALSHA over EVAL?** EVALSHA sends only the script's SHA hash (40 bytes) instead of the full script text on every call. The script is loaded once via SCRIPT LOAD and cached by Redis. Under high throughput, this saves bandwidth.

**Why both FastAPI middleware and Kong plugin?** The middleware protects a single service. The Kong plugin protects at the gateway layer — one rate limiter in front of multiple backend services. Having both demonstrates understanding of where rate limiting belongs in different architectures.

## Tech Stack

- **API:** FastAPI (async Python)
- **State:** Redis 7 (redis-py + hiredis, atomic Lua scripts)
- **Monitoring:** Prometheus + Grafana
- **Gateway:** Kong + Lua (resty.redis)
- **Testing:** pytest (unit), Locust (load)
- **Infrastructure:** Docker Compose
