# -*- coding: utf-8 -*-
"""
Sliding Window Rate Limiter for ComposeBridge WebSocket Server.
Protects the server from flood, denial-of-service, or brute-force attacks.
Default: 60 requests per minute per IP address.
"""

import time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class RateLimiter:
    """
    Sliding window rate limiter tracking request timestamps per client IP.
    Zero external dependencies, highly efficient, thread-safe.
    """

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def is_allowed(self, client_ip: str, max_requests: Optional[int] = None) -> Tuple[bool, int]:
        """
        Check if an incoming request from client_ip is allowed.
        Can override limit with max_requests (e.g. for authenticated clients or sliders).
        If max_requests is 0 or negative, it is treated as unlimited.
        Returns: (is_allowed: bool, remaining_requests_in_window: int)
        """
        effective_limit = max_requests if max_requests is not None else self.max_requests
        if effective_limit <= 0:
            return True, 999999

        now = time.time()
        # Periodic cleanup of idle IPs every 5 minutes
        if now - self._last_cleanup > 300:
            self._cleanup(now)

        timestamps = self._requests[client_ip]
        cutoff = now - self.window_seconds

        # Evict timestamps outside the active sliding window
        while timestamps and timestamps[0] <= cutoff:
            timestamps.pop(0)

        if len(timestamps) >= effective_limit:
            return False, 0

        timestamps.append(now)
        remaining = max(0, effective_limit - len(timestamps))
        return True, remaining

    def _cleanup(self, now: float):
        cutoff = now - self.window_seconds
        stale_ips = [ip for ip, ts in self._requests.items() if not ts or ts[-1] <= cutoff]
        for ip in stale_ips:
            del self._requests[ip]
        self._last_cleanup = now

    def reset(self, client_ip: Optional[str] = None):
        """Reset limiter state for a specific IP or all IPs."""
        if client_ip:
            self._requests.pop(client_ip, None)
        else:
            self._requests.clear()
