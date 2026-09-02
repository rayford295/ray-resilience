"""Hardening policies: pure logic, fake clocks, no HTTP stack needed."""

import unittest

from geosteward.gateway.hardening import (
    SlidingWindowLimiter,
    authorize,
    client_key,
    is_loopback,
    parse_rate_limit,
)


class AuthorizeTest(unittest.TestCase):
    def test_no_token_configured_serves_loopback_only(self):
        ok, _ = authorize(None, None, "127.0.0.1")
        self.assertTrue(ok)
        ok, reason = authorize(None, None, "203.0.113.9")
        self.assertFalse(ok)
        self.assertIn("STEWARD_API_TOKEN", reason)

    def test_configured_token_gates_everyone_including_loopback_without_it(self):
        self.assertTrue(authorize("s3cret", "s3cret", "203.0.113.9")[0])
        self.assertFalse(authorize("s3cret", "wrong", "203.0.113.9")[0])
        self.assertFalse(authorize("s3cret", None, "127.0.0.1")[0])

    def test_loopback_shapes(self):
        for host in ("127.0.0.1", "127.9.9.9", "::1", "localhost"):
            self.assertTrue(is_loopback(host), host)
        for host in ("10.0.0.1", "203.0.113.9", None, ""):
            self.assertFalse(is_loopback(host), host)


class ClientKeyTest(unittest.TestCase):
    def test_forwarded_for_is_honored_only_when_the_deployment_trusts_it(self):
        self.assertEqual(client_key("1.1.1.1", "9.9.9.9, 2.2.2.2", trust_proxy=True), "9.9.9.9")
        # Attacker-writable header without a proxy: the peer stays the identity.
        self.assertEqual(client_key("1.1.1.1", "9.9.9.9", trust_proxy=False), "1.1.1.1")
        self.assertEqual(client_key(None, None, trust_proxy=True), "unknown")


class RateLimitSpecTest(unittest.TestCase):
    def test_parses_the_documented_shape(self):
        self.assertEqual(parse_rate_limit("20/60"), (20, 60.0))

    def test_malformed_and_non_positive_specs_fail_loudly(self):
        for bad in ("20", "a/b", "0/60", "20/0", "20/-5"):
            with self.assertRaises(ValueError, msg=bad):
                parse_rate_limit(bad)


class LimiterTest(unittest.TestCase):
    def test_allows_up_to_the_cap_then_refuses_with_a_retry_hint(self):
        t = [0.0]
        limiter = SlidingWindowLimiter(3, 60, clock=lambda: t[0])
        for _ in range(3):
            self.assertTrue(limiter.allow("a")[0])
        ok, retry = limiter.allow("a")
        self.assertFalse(ok)
        self.assertAlmostEqual(retry, 60.0)

    def test_window_slides_and_keys_are_independent(self):
        t = [0.0]
        limiter = SlidingWindowLimiter(1, 10, clock=lambda: t[0])
        self.assertTrue(limiter.allow("a")[0])
        self.assertFalse(limiter.allow("a")[0])
        self.assertTrue(limiter.allow("b")[0])  # other callers unaffected
        t[0] = 10.1
        self.assertTrue(limiter.allow("a")[0])  # old hit aged out


if __name__ == "__main__":
    unittest.main()
