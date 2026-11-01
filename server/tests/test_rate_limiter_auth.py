# -*- coding: utf-8 -*-
import unittest
from network.rate_limiter import RateLimiter


class TestRateLimiterAuth(unittest.TestCase):
    def test_unauthenticated_rate_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        client_ip = "192.168.1.100"

        # 5 requests should pass
        for i in range(5):
            allowed, remaining = limiter.is_allowed(client_ip)
            self.assertTrue(allowed, f"Request {i+1} should be allowed")

        # 6th request should be blocked
        allowed, remaining = limiter.is_allowed(client_ip)
        self.assertFalse(allowed, "6th unauthenticated request should be blocked")
        self.assertEqual(remaining, 0)

    def test_authenticated_override_rate_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        client_ip = "192.168.1.100"

        # Authenticated clients pass max_requests=1200
        for i in range(50):
            allowed, remaining = limiter.is_allowed(client_ip, max_requests=1200)
            self.assertTrue(allowed, f"Authenticated request {i+1} should be allowed")

    def test_unlimited_rate_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        client_ip = "127.0.0.1"

        allowed, remaining = limiter.is_allowed(client_ip, max_requests=0)
        self.assertTrue(allowed)
        self.assertGreater(remaining, 1000)


if __name__ == "__main__":
    unittest.main()

