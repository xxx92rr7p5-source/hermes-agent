"""Network health check — fast connectivity pre-check to fail fast on network outage.

When the network is down, Hermes API calls (prompt.submit, clarify.respond,
image.attach) and session operations (session.interrupt) hang until the OS-level
TCP timeout (often 60-120s). This module provides a fast, cached connectivity
check that callers can use BEFORE making a network-dependent call, so the user
gets an immediate "Network unavailable" message instead of a cryptic timeout.

Design:
  - TCP socket connect (not HTTP) for minimum latency (~1-3s vs 10-30s for HTTP)
  - Thread-safe result cache with configurable TTL (default 5s)
  - Singleton pattern — one check services all callers in the cache window
  - Works for both sync and async callers
"""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

# ─── Cache ──────────────────────────────────────────────────────────────────────


@dataclass
class _HealthCache:
    """Thread-safe connectivity cache with TTL."""

    available: bool = True
    checked_at: float = 0.0
    ttl: float = 5.0  # seconds
    lock: threading.Lock = field(default_factory=threading.Lock)


_health_cache = _HealthCache()

# ─── Default endpoints to probe ─────────────────────────────────────────────────

# These are the primary endpoints Hermes talks to. We check them in order and
# stop at the first success — if any one is reachable, the network is up.
_DEFAULT_PROBE_HOSTS = [
    ("openrouter.ai", 443),
    ("api.anthropic.com", 443),
    ("api.openai.com", 443),
]

# Short timeout per probe — we're just checking TCP reachability, not doing a
# full TLS handshake.  3 seconds is generous for a SYN-ACK on any reasonable
# connection.
_PROBE_TIMEOUT_S = 3.0


# ─── Public API ─────────────────────────────────────────────────────────────────


def is_network_available(
    *,
    hosts: list[tuple[str, int]] | None = None,
    timeout: float = _PROBE_TIMEOUT_S,
    cache_ttl: float = 5.0,
) -> bool:
    """Return True if at least one probe host is TCP-reachable.

    Results are cached for *cache_ttl* seconds to avoid repeated checks
    in rapid succession (e.g. retry loops).  Pass ``cache_ttl=0`` to
    force a fresh check.

    Args:
        hosts: List of ``(hostname, port)`` tuples to probe.  Defaults to
            OpenRouter, Anthropic, and OpenAI on port 443.
        timeout: Per-probe TCP connect timeout in seconds.
        cache_ttl: How long to cache the result (seconds).  0 = no cache.
    """
    global _health_cache

    now = time.monotonic()
    with _health_cache.lock:
        if cache_ttl > 0 and (now - _health_cache.checked_at) < _health_cache.ttl:
            return _health_cache.available
        _health_cache.checked_at = now
        _health_cache.ttl = cache_ttl

    hosts = hosts or _DEFAULT_PROBE_HOSTS
    available = _probe_any(hosts, timeout)

    with _health_cache.lock:
        _health_cache.available = available

    return available


def check_provider_endpoint(base_url: str, *, timeout: float = 3.0) -> bool:
    """Check if a specific provider base URL is TCP-reachable.

    Extracts host and port from *base_url* and attempts a TCP connect.
    Returns True if the socket connects within *timeout* seconds.

    Args:
        base_url: Provider base URL (e.g. ``"https://openrouter.ai/api/v1"``).
        timeout: TCP connect timeout in seconds.
    """
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except Exception:
        return False

    return _probe_one(host, port, timeout)


def reset_health_cache() -> None:
    """Reset the cached health state so the next check is live."""
    global _health_cache
    with _health_cache.lock:
        _health_cache.available = True
        _health_cache.checked_at = 0.0


def set_network_unavailable() -> None:
    """Force-set the health cache to unavailable (e.g. after a confirmed timeout).

    Call this after a network error is confirmed so that subsequent pre-checks
    fail fast without re-probing.
    """
    global _health_cache
    now = time.monotonic()
    with _health_cache.lock:
        _health_cache.available = False
        _health_cache.checked_at = now
        _health_cache.ttl = 5.0


# ─── Internal ───────────────────────────────────────────────────────────────────


def _probe_one(host: str, port: int, timeout: float) -> bool:
    """Attempt a single TCP connect.  Returns True on success."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (OSError, socket.timeout, socket.gaierror):
        return False


def _probe_any(hosts: list[tuple[str, int]], timeout: float) -> bool:
    """Try each host in order; return True at the first success."""
    for host, port in hosts:
        if _probe_one(host, port, timeout):
            return True
    return False
