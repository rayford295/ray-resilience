"""Zero-shot VLM severity: parsing is strict, metrics are RAPID's, records are
complete, and the network call is injected so none of this needs a model."""

import json
import tempfile
import unittest
from pathlib import Path

from geosteward.deepcase.vlm_severity import (
    WILDFIRE_CLASSES,
    WILDFIRE_PROMPT,
    WILDFIRE_TO_CANONICAL,
    aggregate_h3,
    build_messages,
    classify_image,
    confusion,
    gps_to_latlon,
    ncse,
    normalise_label,
    BITEMPORAL_PROMPT,
    HURRICANE_CLASSES,
    classify_pair,
    parse_prediction,
    sha256_text,
    summarize,
)
from geosteward.gateway.llm import image_part, text_part

# Smallest valid JPEG-ish payload is not needed: classify_image only hashes bytes
# and hands them to the injected call. PNG suffix selects the PNG mime.
FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class TestParsing(unittest.TestCase):
    def test_clean_json(self) -> None:
        p = parse_prediction('{"Predicted_Class": "4_Destroyed_50plus", "Confidence": 0.91}')
        self.assertEqual((p.label, p.confidence, p.status), ("4_Destroyed_50plus", 0.91, "ok"))

    def test_fenced_json_and_prose_wrapping(self) -> None:
        fenced = '```json\n{"Predicted_Class": "2_Minor_10_25", "Confidence": 0.6}\n```'
        self.assertEqual(parse_prediction(fenced).label, "2_Minor_10_25")
        prose = 'Sure. {"Predicted_Class": "0_No_Damage", "Confidence": 0.8} Hope this helps.'
        self.assertEqual(parse_prediction(prose).label, "0_No_Damage")

    def test_ordinal_only_label_resolves_but_free_text_does_not(self) -> None:
        self.assertEqual(normalise_label("3"), "3_Major_26_50")
        self.assertEqual(normalise_label("1 - Affected"), "1_Affected_1_9")
        self.assertEqual(normalise_label("4_destroyed_50plus"), "4_Destroyed_50plus")
        self.assertIsNone(normalise_label("the structure is destroyed"))
        self.assertIsNone(normalise_label(""))
        self.assertIsNone(normalise_label(None))

    def test_unknown_label_and_unparseable_are_distinct_statuses(self) -> None:
        self.assertEqual(parse_prediction('{"Predicted_Class": "Severe", "Confidence": 0.5}').status, "unknown_label")
        self.assertEqual(parse_prediction("I cannot classify this image.").status, "unparseable")
        self.assertEqual(parse_prediction("").status, "unparseable")
        self.assertEqual(parse_prediction("[1, 2, 3]").status, "unparseable")

    def test_confidence_is_clamped_or_none(self) -> None:
        self.assertEqual(parse_prediction('{"Predicted_Class": "0_No_Damage", "Confidence": 1.7}').confidence, 1.0)
        self.assertIsNone(parse_prediction('{"Predicted_Class": "0_No_Damage", "Confidence": "high"}').confidence)

    def test_prompt_is_frozen(self) -> None:
        # The prompt is RAPID's, verbatim; its hash is what run records carry.
        self.assertIn("You are a Wildfire Damage Classifier.", WILDFIRE_PROMPT)
        self.assertEqual(len(sha256_text(WILDFIRE_PROMPT)), 64)
        self.assertEqual(set(WILDFIRE_TO_CANONICAL), set(WILDFIRE_CLASSES))


class TestMetrics(unittest.TestCase):
    def test_ncse_bounds(self) -> None:
        self.assertEqual(ncse([0, 1, 2], [0, 1, 2], 5), 0.0)
        self.assertEqual(ncse([0, 4], [4, 0], 5), 1.0)
        self.assertAlmostEqual(ncse([0, 0], [1, 2], 5), (1 + 2) / (2 * 4))
        with self.assertRaises(ValueError):
            ncse([0], [0, 1], 5)

    def test_confusion_orientation(self) -> None:
        cm = confusion([0, 0, 1], [0, 1, 1], 2)
        self.assertEqual(cm, [[1, 1], [0, 1]])  # rows truth, cols pred

    def test_summary_excludes_unanswered_from_accuracy_but_counts_them(self) -> None:
        recs = [
            {"truth": "0_No_Damage", "pred": "0_No_Damage", "status": "ok"},
            {"truth": "4_Destroyed_50plus", "pred": "3_Major_26_50", "status": "ok"},
            {"truth": "2_Minor_10_25", "pred": None, "status": "unparseable"},
            {"truth": "1_Affected_1_9", "pred": None, "status": "unknown_label"},
        ]
        s = summarize(recs)
        self.assertEqual((s["n_images"], s["n_scored"], s["n_unparseable"], s["n_unknown_label"]), (4, 2, 1, 1))
        self.assertEqual(s["accuracy"], 0.5)
        self.assertEqual(s["adjacent_error_rate"], 0.5)
        self.assertEqual(s["ncse"], round(1 / (2 * 4), 4))
        self.assertEqual(s["per_class"]["4_Destroyed_50plus"]["recall"], 0.0)
        self.assertIsNone(s["per_class"]["2_Minor_10_25"]["recall"])

    def test_summary_on_nothing_scored_reports_none_not_zero(self) -> None:
        s = summarize([{"truth": "0_No_Damage", "pred": None, "status": "unparseable"}])
        self.assertIsNone(s["accuracy"])
        self.assertEqual(s["unanswered_rate"], 1.0)


class TestGeolocation(unittest.TestCase):
    def test_gps_dict_numeric_keys(self) -> None:
        gps = {1: "N", 2: (34.0, 2.0, 30.0), 3: "W", 4: (118.0, 30.0, 0.0)}
        self.assertEqual(gps_to_latlon(gps), (34.041667, -118.5))

    def test_gps_named_keys_and_rejects_null_island(self) -> None:
        gps = {"GPSLatitudeRef": "S", "GPSLatitude": (1, 0, 0), "GPSLongitudeRef": "E", "GPSLongitude": (2, 0, 0)}
        self.assertEqual(gps_to_latlon(gps), (-1.0, 2.0))
        self.assertIsNone(gps_to_latlon({1: "N", 2: (0, 0, 0), 3: "E", 4: (0, 0, 0)}))
        self.assertIsNone(gps_to_latlon({}))


class TestClassifyImage(unittest.TestCase):
    def test_record_is_complete_and_call_receives_image_part(self) -> None:
        seen = {}

        def fake_call(messages, response_format):
            seen["messages"] = messages
            seen["response_format"] = response_format
            return '{"Predicted_Class": "4_Destroyed_50plus", "Confidence": 0.9}'

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            img = root / "4_Destroyed_50plus" / "a.jpg"
            img.parent.mkdir()
            img.write_bytes(FAKE_JPEG)
            rec = classify_image(fake_call, img, "4_Destroyed_50plus", relative_to=root)

        self.assertEqual(rec["image"], "4_Destroyed_50plus/a.jpg")
        self.assertEqual(rec["pred"], "4_Destroyed_50plus")
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(len(rec["image_sha256"]), 64)
        self.assertEqual(len(rec["response_sha256"]), 64)
        self.assertIsNone(rec["error"])
        self.assertIsNone(rec["lat"])
        self.assertEqual(seen["response_format"], {"type": "json_object"})
        content = seen["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertIn("Wildfire Damage Classifier", content[0]["text"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_endpoint_failure_is_recorded_not_fabricated(self) -> None:
        def broken(messages, response_format):
            raise ConnectionError("refused")

        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "x.png"
            img.write_bytes(FAKE_JPEG)
            rec = classify_image(broken, img, "0_No_Damage")
        self.assertEqual(rec["status"], "unparseable")
        self.assertIsNone(rec["pred"])
        self.assertIn("ConnectionError", rec["error"])
        self.assertIsNone(rec["response_sha256"])

    def test_png_suffix_selects_png_mime(self) -> None:
        msgs = build_messages(FAKE_JPEG, "p", "image/png")
        self.assertTrue(msgs[0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))


class TestAggregate(unittest.TestCase):
    def test_tiles_carry_histograms_and_never_coordinates(self) -> None:
        recs = [
            {"lat": 34.05, "lon": -118.55, "truth": "4_Destroyed_50plus", "pred": "4_Destroyed_50plus", "status": "ok"},
            {"lat": 34.05, "lon": -118.55, "truth": "4_Destroyed_50plus", "pred": "3_Major_26_50", "status": "ok"},
            {"lat": 34.05, "lon": -118.55, "truth": "0_No_Damage", "pred": None, "status": "unparseable"},
            {"lat": None, "lon": None, "truth": "0_No_Damage", "pred": "0_No_Damage", "status": "ok"},
        ]
        feats = aggregate_h3(recs)
        self.assertEqual(len(feats), 1)
        p = feats[0]["properties"]
        self.assertEqual((p["n_samples"], p["n_scored"], p["agreement_rate"]), (3, 2, 0.5))
        self.assertEqual(p["labels_truth"], {"0_No_Damage": 1, "4_Destroyed_50plus": 2})
        self.assertEqual(p["labels_pred"], {"3_Major_26_50": 1, "4_Destroyed_50plus": 1})
        self.assertTrue(p["uncertainty"]["model_derived"])
        self.assertEqual(p["uncertainty"]["n_unanswered"], 1)
        self.assertFalse(p["uncertainty"]["low_n"])
        self.assertNotIn("lat", json.dumps(p))
        self.assertEqual(feats[0]["geometry"]["type"], "Polygon")


class TestPairs(unittest.TestCase):
    RESPONSE = json.dumps({
        "Predicted_Severity": "Severe", "Confidence_Score": 0.8,
        "Objects_Detected": {"debris_pile": 1, "fallen_tree": "1", "flooded_road": 0, "damaged_building": True, "downed_lines": 2},
        "Reasoning": "Roof gone, debris across the road.",
    })

    def test_severity_key_objects_and_reasoning_digest(self) -> None:
        p = parse_prediction(self.RESPONSE, HURRICANE_CLASSES)
        self.assertEqual((p.label, p.confidence, p.status), ("Severe", 0.8, "ok"))
        # 2 is not a binary indicator: dropped, not coerced
        self.assertEqual(p.objects, {"debris_pile": 1, "fallen_tree": 1, "flooded_road": 0, "damaged_building": 1})
        self.assertEqual(len(p.reasoning_sha256), 64)
        self.assertEqual(p.reasoning_chars, len("Roof gone, debris across the road."))

    def test_truth_labels_normalise_case(self) -> None:
        self.assertEqual(normalise_label("mild", HURRICANE_CLASSES), "Mild")
        self.assertIsNone(normalise_label("4_Destroyed_50plus", HURRICANE_CLASSES))

    def test_pair_record_orders_pre_then_post_and_keeps_given_location(self) -> None:
        seen = {}

        def fake_call(messages, response_format):
            seen["content"] = messages[0]["content"]
            return self.RESPONSE

        with tempfile.TemporaryDirectory() as tmp:
            pre = Path(tmp) / "111_2023.png"; post = Path(tmp) / "222_2024.png"
            pre.write_bytes(b"PRE" + FAKE_JPEG); post.write_bytes(b"POST" + FAKE_JPEG)
            rec = classify_pair(fake_call, pre, post, "Severe", latlon=(29.44, -83.29), pair_id="111_vs_222")
        self.assertEqual(len(seen["content"]), 3)
        self.assertIn("Pre-disaster baseline (2023)", seen["content"][0]["text"])
        self.assertEqual(seen["content"][0]["text"], BITEMPORAL_PROMPT)
        self.assertNotEqual(seen["content"][1]["image_url"]["url"], seen["content"][2]["image_url"]["url"])
        self.assertEqual((rec["pair_id"], rec["truth"], rec["pred"], rec["status"]), ("111_vs_222", "Severe", "Severe", "ok"))
        self.assertEqual((rec["lat"], rec["lon"]), (29.44, -83.29))
        self.assertNotEqual(rec["pre_sha256"], rec["post_sha256"])
        self.assertNotIn("Reasoning", json.dumps(rec))  # prose hashed, not stored


class TestLLMParts(unittest.TestCase):
    def test_parts_shape(self) -> None:
        self.assertEqual(text_part("hi"), {"type": "text", "text": "hi"})
        part = image_part(b"abc", "image/png")
        self.assertEqual(part["type"], "image_url")
        self.assertEqual(part["image_url"]["url"], "data:image/png;base64,YWJj")


if __name__ == "__main__":
    unittest.main()
