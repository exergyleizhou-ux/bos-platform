"""
BOS Pipeline v9.0 -Middleware Package

Custom middleware stack:
- RequestIDMiddleware: Adds X-Request-ID to every request
- TimingMiddleware: Measures and logs request duration
- TenantMiddleware: Extracts tenant context from JWT
- RateLimitMiddleware: Per-tenant rate limiting
- CORSMiddleware: Cross-origin resource sharing (via FastAPI built-in)
"""
