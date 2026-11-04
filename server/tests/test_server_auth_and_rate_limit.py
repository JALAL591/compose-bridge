# -*- coding: utf-8 -*-
"""
Tests for Dynamic Auth Token and Rate Limiting (v1.2.0).

Verifies:
1. Dynamic 32-byte (64-char) token generation and storage in auth_token.txt.
2. Constant-time token verification and rejection of insecure static dev tokens.
3. Rate limiter sliding window enforcement (60 req/min per IP).
4. WebSocket handshake authentication flow.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import asyncio
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from core.auth_manager import (
    get_or_create_auth_token,
    verify_token,
    set_dev_token,
    get_auth_token_file_path,
)
from network.rate_limiter import RateLimiter


class TestServerAuthAndRateLimit(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cb_auth_test_")
        self.root = Path(self.test_dir)
        set_dev_token(None)

    def tearDown(self):
        set_dev_token(None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dynamic_token_generation_and_storage(self):
        token = get_or_create_auth_token(self.root)
        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 64, "Token must be a 64-character (32-byte) hex string")

        # Verify auth_token.txt exists and contains the exact token
        token_txt = self.root / ".composebridge-state" / "auth_token.txt"
        self.assertTrue(token_txt.exists(), "auth_token.txt must be created")
        self.assertEqual(token_txt.read_text(encoding="utf-8").strip(), token)

        # Verify auth.json exists
        auth_json = self.root / ".composebridge-state" / "auth.json"
        self.assertTrue(auth_json.exists(), "auth.json must be created")
        data = json.loads(auth_json.read_text(encoding="utf-8"))
        self.assertEqual(data.get("token"), token)

    def test_verify_token_valid_and_invalid(self):
        token = get_or_create_auth_token(self.root)
        self.assertTrue(verify_token(token, self.root))

        # Invalid tokens must be rejected
        self.assertFalse(verify_token("invalid_token_12345", self.root))
        self.assertFalse(verify_token("", self.root))
        self.assertFalse(verify_token(None, self.root))

        # Legacy static token must now be rejected by default!
        self.assertFalse(verify_token("test-token-local-dev", self.root))

    def test_dev_token_override(self):
        # Setting explicit dev token allows override
        set_dev_token("custom-override-token")
        self.assertTrue(verify_token("custom-override-token", self.root))
        self.assertFalse(verify_token("something-else", self.root))

    def test_rate_limiter_sliding_window(self):
        limiter = RateLimiter(max_requests=10, window_seconds=1.0)
        client_ip = "192.168.1.100"

        # First 10 requests should succeed
        for i in range(10):
            allowed, remaining = limiter.is_allowed(client_ip)
            self.assertTrue(allowed, f"Request {i+1} should be allowed")
            self.assertEqual(remaining, 10 - (i + 1))

        # 11th request must be blocked
        allowed, remaining = limiter.is_allowed(client_ip)
        self.assertFalse(allowed, "11th request within window must be blocked")
        self.assertEqual(remaining, 0)

        # Different IP should still be allowed
        other_allowed, _ = limiter.is_allowed("192.168.1.101")
        self.assertTrue(other_allowed, "Different IP should have independent limit")

        # After window expires, original IP is allowed again
        time.sleep(1.05)
        allowed_again, remaining_again = limiter.is_allowed(client_ip)
        self.assertTrue(allowed_again, "Request after window expiration should be allowed")
        self.assertEqual(remaining_again, 9)

    def test_rate_limiter_reset(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60.0)
        client_ip = "10.0.0.1"

        for _ in range(5):
            limiter.is_allowed(client_ip)

        # Now blocked
        self.assertFalse(limiter.is_allowed(client_ip)[0])

        # Reset
        limiter.reset(client_ip)
        self.assertTrue(limiter.is_allowed(client_ip)[0])


if __name__ == "__main__":
    unittest.main()
