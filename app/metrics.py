from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

REQUEST_COUNT = Counter(
    "ratemaster_requests_total",
    "Total rate-limited requests",
    ["algorithm", "route", "result"],
)

LATENCY = Histogram(
    "ratemaster_latency_seconds",
    "Time spent in rate-limit check",
    ["algorithm", "route"],
)

ACTIVE_KEYS = Gauge(
    "ratemaster_active_keys",
    "Number of active rate-limit keys",
    ["algorithm"],
)

metrics_app = make_asgi_app()

