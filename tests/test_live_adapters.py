"""The real adapters, against a local stub.

What this establishes and what it does not: these tests pin down how
`places.py` and `grounded.py` behave — what they send, what they parse, and how
they fail — against an HTTP server in this process. They are not evidence that
either integration works against Google, which has never been executed (design
§10, blocker 1: no key). That distinction is the whole reason the adapters raise
`LiveUnavailable` on every unexpected shape instead of returning a partial
result: an untested wire format should produce a declared outage, not a
confident attestation to a response nobody parsed correctly.
"""

import json
import os
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import patch

import h3

from geosteward.live.base import CITED_ONLY, RE_DERIVABLE, LiveUnavailable, response_digest
from geosteward.live.grounded import GroundedMapsSource
from geosteward.live.places import DEFAULT_FIELDS, PlacesSource, build_request

CELL = h3.latlng_to_cell(34.1897, -118.1312, 9)

PLACES_RESPONSE = {
    "places": [
        {
            "id": "STUB_PLACE_1",
            "displayName": {"text": "Stub Regional Hospital"},
            "primaryType": "hospital",
            "location": {"latitude": 34.19, "longitude": -118.13},
        },
        {
            "id": "STUB_PLACE_2",
            "displayName": {"text": "Stub Fire Station 4"},
            "primaryType": "fire_station",
            "location": {"latitude": 34.188, "longitude": -118.134},
        },
    ]
}

GROUNDED_RESPONSE = {
    "candidates": [
        {
            "content": {"parts": [{"text": "A hospital and a fire station are nearby."}]},
            "groundingMetadata": {
                "groundingChunks": [
                    {"maps": {"placeId": "STUB_PLACE_1", "title": "Stub Regional Hospital"}},
                    {"maps": {"placeId": "STUB_PLACE_2", "title": "Stub Fire Station 4"}},
                ]
            },
        }
    ]
}


class _Handler(BaseHTTPRequestHandler):
    #: Mutated per test by `StubServer`.
    response_body: dict = {}
    status_code: int = 200
    seen: dict = {}

    def do_POST(self) -> None:  # noqa: N802  (stdlib naming)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        type(self).seen = {
            "path": self.path,
            # Lowercased: HTTP header names are case-insensitive and `urllib`
            # normalises the case it sends, so a plain dict keyed on the
            # original spelling would assert against urllib's formatting rather
            # than against what was requested.
            "headers": {name.lower(): value for name, value in self.headers.items()},
            "body": json.loads(raw),
        }
        body = json.dumps(type(self).response_body).encode("utf-8")
        self.send_response(type(self).status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # keep the test output readable
        return


class StubServer:
    def __init__(self, response_body: dict, status_code: int = 200):
        _Handler.response_body = response_body
        _Handler.status_code = status_code
        _Handler.seen = {}
        self.httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self) -> "StubServer":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def seen(self) -> dict:
        return _Handler.seen


class TestPlacesSource(unittest.TestCase):
    def test_missing_key_is_a_declared_outage(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STEWARD_GMP_API_KEY", None)
            with self.assertRaises(LiveUnavailable) as ctx:
                PlacesSource().lookup(build_request(CELL))
        self.assertIn("STEWARD_GMP_API_KEY", str(ctx.exception))

    def test_declares_itself_re_derivable_and_unretained(self) -> None:
        source = PlacesSource()
        self.assertEqual(source.verifiability, RE_DERIVABLE)
        self.assertEqual(source.license, "third-party-restricted")
        self.assertEqual(source.retention, "not-retained")
        self.assertEqual(source.attribution, "Google")

    def test_successful_lookup_returns_digest_and_content_separately(self) -> None:
        with StubServer(PLACES_RESPONSE) as server:
            with patch.dict(
                os.environ,
                {"STEWARD_GMP_API_KEY": "test-key", "STEWARD_PLACES_BASE_URL": server.base_url},
            ):
                result = PlacesSource().lookup(build_request(CELL))

        self.assertEqual(result.n_results, 2)
        self.assertEqual(result.reference_ids, ("STUB_PLACE_1", "STUB_PLACE_2"))
        self.assertEqual(result.response_sha256, response_digest(PLACES_RESPONSE))
        # The content came back to the caller for rendering; keeping it out of
        # the record is the recorder's job, not the adapter's.
        self.assertEqual(result.display_payload, PLACES_RESPONSE)

    def test_request_is_scoped_by_the_tile_not_a_point(self) -> None:
        with StubServer(PLACES_RESPONSE) as server:
            with patch.dict(
                os.environ,
                {"STEWARD_GMP_API_KEY": "test-key", "STEWARD_PLACES_BASE_URL": server.base_url},
            ):
                PlacesSource().lookup(build_request(CELL, radius_m=900))
            sent = server.seen

        centre = sent["body"]["locationRestriction"]["circle"]["center"]
        cell_lat, cell_lon = h3.cell_to_latlng(CELL)
        self.assertAlmostEqual(centre["latitude"], cell_lat, places=9)
        self.assertAlmostEqual(centre["longitude"], cell_lon, places=9)
        self.assertEqual(sent["body"]["locationRestriction"]["circle"]["radius"], 900.0)
        # The caller's own coordinates were never in the request to begin with.
        self.assertNotIn("34.1897", json.dumps(sent["body"]))

    def test_field_mask_asks_only_for_the_declared_fields(self) -> None:
        with StubServer(PLACES_RESPONSE) as server:
            with patch.dict(
                os.environ,
                {"STEWARD_GMP_API_KEY": "test-key", "STEWARD_PLACES_BASE_URL": server.base_url},
            ):
                PlacesSource().lookup(build_request(CELL))
            mask = server.seen["headers"]["x-goog-fieldmask"]

        self.assertEqual(mask, ",".join(f"places.{name}" for name in DEFAULT_FIELDS))
        for forbidden in ("rating", "userRatingCount", "reviews", "photos", "phone"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, mask)

    def test_empty_result_is_an_answer_not_a_failure(self) -> None:
        with StubServer({"places": []}) as server:
            with patch.dict(
                os.environ,
                {"STEWARD_GMP_API_KEY": "test-key", "STEWARD_PLACES_BASE_URL": server.base_url},
            ):
                result = PlacesSource().lookup(build_request(CELL))
        self.assertEqual(result.n_results, 0)
        self.assertEqual(result.reference_ids, ())

    def test_unexpected_shape_is_an_outage_not_a_partial_result(self) -> None:
        with StubServer({"places": "not-a-list"}) as server:
            with patch.dict(
                os.environ,
                {"STEWARD_GMP_API_KEY": "test-key", "STEWARD_PLACES_BASE_URL": server.base_url},
            ):
                with self.assertRaises(LiveUnavailable):
                    PlacesSource().lookup(build_request(CELL))

    def test_http_error_is_an_outage(self) -> None:
        with StubServer({"error": {"status": "PERMISSION_DENIED"}}, status_code=403) as server:
            with patch.dict(
                os.environ,
                {"STEWARD_GMP_API_KEY": "bad-key", "STEWARD_PLACES_BASE_URL": server.base_url},
            ):
                with self.assertRaises(LiveUnavailable):
                    PlacesSource().lookup(build_request(CELL))


class TestGroundedMapsSource(unittest.TestCase):
    def test_missing_key_is_a_declared_outage(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STEWARD_GEMINI_API_KEY", None)
            with self.assertRaises(LiveUnavailable) as ctx:
                GroundedMapsSource().ask("What is near here?", {"h3_cell": CELL})
        self.assertIn("STEWARD_GEMINI_API_KEY", str(ctx.exception))

    def test_declares_itself_cited_only(self) -> None:
        self.assertEqual(GroundedMapsSource().verifiability, CITED_ONLY)

    def test_grounded_answer_returns_text_and_citations(self) -> None:
        with StubServer(GROUNDED_RESPONSE) as server:
            with patch.dict(
                os.environ,
                {
                    "STEWARD_GEMINI_API_KEY": "test-key",
                    "STEWARD_GEMINI_BASE_URL": server.base_url,
                },
            ):
                result = GroundedMapsSource().ask("What is near here?", {"h3_cell": CELL})
            sent = server.seen

        self.assertIn("hospital", result.text)
        self.assertEqual(result.citations, ("STUB_PLACE_1", "STUB_PLACE_2"))
        self.assertEqual(sent["body"]["tools"], [{"google_maps": {}}])
        self.assertIn(CELL, sent["body"]["contents"][0]["parts"][0]["text"])

    def test_result_has_no_digest_field_to_mistake_for_an_anchor(self) -> None:
        with StubServer(GROUNDED_RESPONSE) as server:
            with patch.dict(
                os.environ,
                {
                    "STEWARD_GEMINI_API_KEY": "test-key",
                    "STEWARD_GEMINI_BASE_URL": server.base_url,
                },
            ):
                result = GroundedMapsSource().ask("What is near here?", {"h3_cell": CELL})
        self.assertFalse(hasattr(result, "response_sha256"))

    def test_prose_without_citations_is_refused(self) -> None:
        # The failure mode this regime has to rule out: an ungrounded paragraph
        # that reads exactly like a grounded one.
        ungrounded = {
            "candidates": [
                {"content": {"parts": [{"text": "There is a hospital nearby."}]}}
            ]
        }
        with StubServer(ungrounded) as server:
            with patch.dict(
                os.environ,
                {
                    "STEWARD_GEMINI_API_KEY": "test-key",
                    "STEWARD_GEMINI_BASE_URL": server.base_url,
                },
            ):
                with self.assertRaises(LiveUnavailable) as ctx:
                    GroundedMapsSource().ask("What is near here?", {"h3_cell": CELL})
        self.assertIn("citation", str(ctx.exception).lower())

    def test_missing_candidates_is_an_outage(self) -> None:
        with StubServer({"candidates": []}) as server:
            with patch.dict(
                os.environ,
                {
                    "STEWARD_GEMINI_API_KEY": "test-key",
                    "STEWARD_GEMINI_BASE_URL": server.base_url,
                },
            ):
                with self.assertRaises(LiveUnavailable):
                    GroundedMapsSource().ask("What is near here?", {"h3_cell": CELL})


if __name__ == "__main__":
    unittest.main()
