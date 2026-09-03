"""Zero-shot VLM severity grading of street-view imagery, evaluated against labels.

Ported from the RAPID line (Yang et al. 2026, arXiv 2606.21819): the Damage
Recognition Agent's wildfire prompt is kept verbatim so results are comparable
to the paper's Dataset C2 numbers. What changes is everything around the call:

* the model is any OpenAI-compatible vision endpoint — a local Ollama model by
  default — so no key and no third-party service is required to reproduce;
* every prediction is a record (image sha256, label, prediction, confidence,
  response sha256, latency), and an unparseable answer is RECORDED as
  unparseable, never coerced into a class;
* the output is an evaluation (accuracy, NCSE, confusion) plus tile-level
  aggregates, and the evaluation decides whether the predictions may ever
  back a claim. Model output is `model_derived` evidence: it carries its
  own accuracy alongside it or it carries nothing.

Pure logic lives here; the network call is injected so tests never need a
model.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from geosteward.deepcase.dins import CANONICAL_SCALE

#: RAPID Dataset C2 classes (LA DINS 2025 folder labels), ordinal 0..4.
WILDFIRE_CLASSES: tuple[str, ...] = (
    "0_No_Damage",
    "1_Affected_1_9",
    "2_Minor_10_25",
    "3_Major_26_50",
    "4_Destroyed_50plus",
)

#: The same five steps on the project's canonical severity scale, via the
#: registry crosswalk for CAL FIRE DINS percent-loss (dins.py).
WILDFIRE_TO_CANONICAL: dict[str, str] = {
    "0_No_Damage": "none",
    "1_Affected_1_9": "minor",
    "2_Minor_10_25": "moderate",
    "3_Major_26_50": "severe",
    "4_Destroyed_50plus": "destroyed",
}
assert set(WILDFIRE_TO_CANONICAL.values()) <= set(CANONICAL_SCALE)

#: RAPID "Damage Recognition Agent" prompt C, verbatim (Prompt--Damage
#: Recognition Agent). Frozen here and hashed into every run record so a
#: later prompt edit is visible as a different prompt_sha256, not a silent
#: change in the numbers.
WILDFIRE_PROMPT = """You are a Wildfire Damage Classifier.

Classify the PRIMARY residential structure using one of the following categories:
1. 0_No_Damage: Structure fully intact.
2. 1_Affected_1_9: Very minor cosmetic effects; structure stable.
3. 2_Minor_10_25: Non-structural damage (broken windows, melted siding).
4. 3_Major_26_50: Significant structural damage; uninhabitable.
5. 4_Destroyed_50plus: Total structural loss or collapse.

Instructions:
- Focus ONLY on the main building.
- Ignore burned trees unless they impact the structure.
- Output STRICT JSON.

Output format:
{
  "Predicted_Class": "...",
  "Confidence": <float>
}
"""


#: The Eaton matched set's 3-class repairability labels (EATON_wildfire_
#: mapillary_matched `label_name`), ordinal 0..2. Derived from CAL FIRE DINS
#: by that dataset's own protocol, so the 5-class DINS prompt collapses onto
#: it by DINS semantics rather than by a new prompt: `Affected (1-9 %)` is
#: trace damage, `Minor` and `Major` are repairable, `Destroyed` is destroyed.
REPAIRABILITY_CLASSES: tuple[str, ...] = ("no_or_trace_damage", "damaged_repairable", "destroyed")

REPAIRABILITY_TO_CANONICAL: dict[str, str] = {
    "no_or_trace_damage": "none",
    "damaged_repairable": "moderate",
    "destroyed": "destroyed",
}
assert set(REPAIRABILITY_TO_CANONICAL.values()) <= set(CANONICAL_SCALE)

DINS5_TO_REPAIRABILITY3: dict[str, str] = {
    "0_No_Damage": "no_or_trace_damage",
    "1_Affected_1_9": "no_or_trace_damage",
    "2_Minor_10_25": "damaged_repairable",
    "3_Major_26_50": "damaged_repairable",
    "4_Destroyed_50plus": "destroyed",
}
assert set(DINS5_TO_REPAIRABILITY3) == set(WILDFIRE_CLASSES)
assert set(DINS5_TO_REPAIRABILITY3.values()) == set(REPAIRABILITY_CLASSES)


def collapse_wildfire_prediction(label: str | None) -> str | None:
    """A 5-class DINS prediction on the 3-class repairability scale, or None
    for no prediction. Only the five offered names collapse; anything else is
    a KeyError, because a label that is not one of the prompt's classes should
    have been recorded as `unknown_label` upstream, never reached here."""
    if label is None:
        return None
    return DINS5_TO_REPAIRABILITY3[label]


#: RAPID Datasets A/B classes (CVDisaster / Bi-Temporal), ordinal 0..2.
HURRICANE_CLASSES: tuple[str, ...] = ("Mild", "Moderate", "Severe")

HURRICANE_TO_CANONICAL: dict[str, str] = {"Mild": "minor", "Moderate": "moderate", "Severe": "severe"}
assert set(HURRICANE_TO_CANONICAL.values()) <= set(CANONICAL_SCALE)

#: RAPID "Damage Recognition Agent" prompt B (pre/post street-view pair), verbatim.
BITEMPORAL_PROMPT = """You are an expert Disaster Assessment AI.
You are provided with two Street View Images of the SAME location:
- Image 1: Pre-disaster baseline (2023)
- Image 2: Post-disaster scene (2024)

Task 1: Comparative Damage Grading
Assess severity of change between the pre- and post-disaster images:
- Mild: Minimal change; branches or small debris but structures unchanged.
- Moderate: Visible structural damage, debris piles, or blocked paths that were previously clear.
- Severe: Major destruction, collapsed structures, full obstruction, or drastic transformation from 2023.

Task 2: Object Detection (Post-disaster image only)
Detect the following (0 = No, 1 = Yes):
- debris_pile
- fallen_tree
- flooded_road
- damaged_building
- downed_lines

Output Requirement:
{
  "Predicted_Severity": "Mild" or "Moderate" or "Severe",
  "Confidence_Score": <float>,
  "Objects_Detected": {
    "debris_pile": 0 or 1,
    "fallen_tree": 0 or 1,
    "flooded_road": 0 or 1,
    "damaged_building": 0 or 1,
    "downed_lines": 0 or 1
  },
  "Reasoning": "Explain key visual differences from 2023 to 2024."
}
"""

OBJECT_KEYS: tuple[str, ...] = ("debris_pile", "fallen_tree", "flooded_road", "damaged_building", "downed_lines")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# Parsing: strict, fail-closed
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Prediction:
    label: str | None
    confidence: float | None
    status: str  # ok | unparseable | unknown_label
    objects: dict[str, int] | None = None  # RAPID's binary object indicators, when the prompt asks for them
    reasoning_sha256: str | None = None  # model prose is hashed, not stored, in the record
    reasoning_chars: int = 0


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text.strip())


def _first_json_object(text: str) -> dict[str, Any] | None:
    text = _strip_fences(text)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # Some models wrap the object in prose; take the outermost {...}.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def normalise_label(raw: Any, classes: Iterable[str] = WILDFIRE_CLASSES) -> str | None:
    """Map a model's class string onto one of `classes`, or None.

    Accepts the exact name, the name with different case/spacing, or the
    bare leading ordinal ("4", "4_", "4 - Destroyed"). It does NOT guess
    from free text such as "the house is destroyed": a label that is not
    one of the offered names is an unknown label, and is recorded as such.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    classes = tuple(classes)
    by_norm = {c.lower().replace(" ", "_"): c for c in classes}
    key = text.lower().replace(" ", "_").replace("-", "_")
    if key in by_norm:
        return by_norm[key]
    m = re.match(r"^\s*(\d)(?:[\s_\-:.]|$)", text)
    if m:
        for c in classes:
            if c.startswith(f"{m.group(1)}_"):
                return c
    return None


def parse_prediction(text: str, classes: Iterable[str] = WILDFIRE_CLASSES) -> Prediction:
    obj = _first_json_object(text)
    if obj is None:
        return Prediction(None, None, "unparseable")
    raw_label = None
    for key in ("Predicted_Class", "predicted_class", "Predicted_Severity", "predicted_severity"):
        if key in obj:
            raw_label = obj[key]
            break
    label = normalise_label(raw_label, classes)
    conf_raw = None
    for key in ("Confidence", "confidence", "Confidence_Score", "confidence_score"):
        if key in obj:
            conf_raw = obj[key]
            break
    confidence: float | None
    try:
        confidence = None if conf_raw is None else max(0.0, min(1.0, float(conf_raw)))
    except (TypeError, ValueError):
        confidence = None
    objects = _parse_objects(obj.get("Objects_Detected", obj.get("Objects")))
    reasoning = obj.get("Reasoning")
    reasoning_sha = sha256_text(str(reasoning)) if isinstance(reasoning, str) and reasoning else None
    reasoning_chars = len(reasoning) if isinstance(reasoning, str) else 0
    if label is None:
        return Prediction(None, confidence, "unknown_label", objects, reasoning_sha, reasoning_chars)
    return Prediction(label, confidence, "ok", objects, reasoning_sha, reasoning_chars)


def _parse_objects(raw: Any) -> dict[str, int] | None:
    """Binary indicators, strictly 0/1 per known key; anything else is dropped
    (a missing indicator is missing, not 0)."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    for key in OBJECT_KEYS:
        v = raw.get(key)
        if isinstance(v, bool):
            out[key] = int(v)
        elif isinstance(v, (int, float)) and v in (0, 1):
            out[key] = int(v)
        elif isinstance(v, str) and v.strip() in ("0", "1"):
            out[key] = int(v.strip())
    return out or None


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def ncse(y_true: list[int], y_pred: list[int], k: int) -> float:
    """Normalized Cross-Severity Error (RAPID): mean |y - ŷ| / (K - 1)."""
    if not y_true:
        return 0.0
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred differ in length")
    if k < 2:
        raise ValueError("k must be >= 2")
    return sum(abs(a - b) for a, b in zip(y_true, y_pred)) / (len(y_true) * (k - 1))


def confusion(y_true: list[int], y_pred: list[int], k: int) -> list[list[int]]:
    """rows = truth, cols = prediction."""
    m = [[0] * k for _ in range(k)]
    for a, b in zip(y_true, y_pred):
        m[a][b] += 1
    return m


def summarize(records: list[dict[str, Any]], classes: tuple[str, ...] = WILDFIRE_CLASSES) -> dict[str, Any]:
    """Evaluation over prediction records. Unparseable / unknown-label
    answers are counted, excluded from accuracy, and reported — the model's
    refusal to answer in-schema is a result, not a missing value."""
    idx = {c: i for i, c in enumerate(classes)}
    k = len(classes)
    scored = [r for r in records if r["status"] == "ok" and r["truth"] in idx]
    y_true = [idx[r["truth"]] for r in scored]
    y_pred = [idx[r["pred"]] for r in scored]
    n = len(records)
    n_scored = len(scored)
    correct = sum(1 for a, b in zip(y_true, y_pred) if a == b)
    adjacent = sum(1 for a, b in zip(y_true, y_pred) if abs(a - b) == 1)
    cm = confusion(y_true, y_pred, k)
    per_class = {}
    for i, c in enumerate(classes):
        support = sum(cm[i])
        per_class[c] = {
            "support": support,
            "recall": round(cm[i][i] / support, 4) if support else None,
        }
    n_unparseable = sum(1 for r in records if r["status"] == "unparseable")
    n_unknown = sum(1 for r in records if r["status"] == "unknown_label")
    return {
        "n_images": n,
        "n_scored": n_scored,
        "n_unparseable": n_unparseable,
        "n_unknown_label": n_unknown,
        "unanswered_rate": round((n_unparseable + n_unknown) / n, 4) if n else None,
        "accuracy": round(correct / n_scored, 4) if n_scored else None,
        "ncse": round(ncse(y_true, y_pred, k), 4) if n_scored else None,
        "adjacent_error_rate": round(adjacent / n_scored, 4) if n_scored else None,
        "classes": list(classes),
        "confusion_rows_truth_cols_pred": cm,
        "per_class": per_class,
    }


# --------------------------------------------------------------------------
# Geolocation from EXIF (optional; enables tile aggregation)
# --------------------------------------------------------------------------

def _dms_to_deg(dms: Any, ref: str | None) -> float | None:
    try:
        d, m, s = (float(x) for x in dms)
    except (TypeError, ValueError):
        return None
    deg = d + m / 60.0 + s / 3600.0
    if ref and ref.upper() in ("S", "W"):
        deg = -deg
    return deg


def gps_to_latlon(gps: dict[Any, Any]) -> tuple[float, float] | None:
    """EXIF GPSInfo dict (numeric or named keys) -> (lat, lon), or None."""
    def get(num: int, name: str) -> Any:
        return gps.get(num, gps.get(name))

    lat = _dms_to_deg(get(2, "GPSLatitude"), get(1, "GPSLatitudeRef"))
    lon = _dms_to_deg(get(4, "GPSLongitude"), get(3, "GPSLongitudeRef"))
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None
    return (round(lat, 6), round(lon, 6))


def exif_latlon(path: Path) -> tuple[float, float] | None:
    try:
        from PIL import Image  # optional dependency
    except ImportError:  # pragma: no cover
        return None
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            gps = exif.get_ifd(0x8825) if hasattr(exif, "get_ifd") else exif.get(0x8825)
    except Exception:
        return None
    if not gps:
        return None
    return gps_to_latlon(dict(gps))


# --------------------------------------------------------------------------
# One image -> one record
# --------------------------------------------------------------------------

#: The injected call: (messages, response_format) -> assistant text.
VisionCall = Callable[[list[dict[str, Any]], dict[str, Any] | None], str]


def build_messages(image_bytes: bytes, prompt: str, mime: str = "image/jpeg") -> list[dict[str, Any]]:
    from geosteward.gateway.llm import image_part, text_part

    return [{"role": "user", "content": [text_part(prompt), image_part(image_bytes, mime)]}]


def classify_image(
    call: VisionCall,
    image_path: Path,
    truth: str | None,
    *,
    prompt: str = WILDFIRE_PROMPT,
    classes: tuple[str, ...] = WILDFIRE_CLASSES,
    relative_to: Path | None = None,
    want_json: bool = True,
) -> dict[str, Any]:
    data = image_path.read_bytes()
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    messages = build_messages(data, prompt, mime)
    started = time.perf_counter()
    try:
        text = call(messages, {"type": "json_object"} if want_json else None)
        error = None
    except Exception as exc:  # the endpoint failed; record it, never fabricate
        text, error = "", f"{type(exc).__name__}: {exc}"
    latency = round(time.perf_counter() - started, 3)
    pred = parse_prediction(text, classes) if text else Prediction(None, None, "unparseable")
    latlon = exif_latlon(image_path)
    rel = image_path.relative_to(relative_to).as_posix() if relative_to else image_path.name
    return {
        "image": rel,
        "image_sha256": sha256_bytes(data),
        "truth": truth,
        "pred": pred.label,
        "confidence": pred.confidence,
        "status": pred.status,
        "response_sha256": sha256_text(text) if text else None,
        "response_chars": len(text),
        "error": error,
        "latency_s": latency,
        "lat": latlon[0] if latlon else None,
        "lon": latlon[1] if latlon else None,
    }


def build_pair_messages(pre_bytes: bytes, post_bytes: bytes, prompt: str, mime: str = "image/png") -> list[dict[str, Any]]:
    """Image 1 = pre, Image 2 = post, in that order — the prompt names them so."""
    from geosteward.gateway.llm import image_part, text_part

    return [{"role": "user", "content": [text_part(prompt), image_part(pre_bytes, mime), image_part(post_bytes, mime)]}]


def classify_pair(
    call: VisionCall,
    pre_path: Path,
    post_path: Path,
    truth: str | None,
    *,
    latlon: tuple[float, float] | None,
    prompt: str = BITEMPORAL_PROMPT,
    classes: tuple[str, ...] = HURRICANE_CLASSES,
    pair_id: str | None = None,
    want_json: bool = True,
) -> dict[str, Any]:
    """One pre/post pair -> one record. Location comes from the dataset's own
    metadata (`latlon`), not EXIF, so it is recorded as given."""
    pre = pre_path.read_bytes()
    post = post_path.read_bytes()
    mime = "image/png" if post_path.suffix.lower() == ".png" else "image/jpeg"
    messages = build_pair_messages(pre, post, prompt, mime)
    started = time.perf_counter()
    try:
        text = call(messages, {"type": "json_object"} if want_json else None)
        error = None
    except Exception as exc:
        text, error = "", f"{type(exc).__name__}: {exc}"
    latency = round(time.perf_counter() - started, 3)
    pred = parse_prediction(text, classes) if text else Prediction(None, None, "unparseable")
    return {
        "pair_id": pair_id or f"{pre_path.stem}_vs_{post_path.stem}",
        "pre_image": pre_path.name,
        "post_image": post_path.name,
        "pre_sha256": sha256_bytes(pre),
        "post_sha256": sha256_bytes(post),
        "truth": truth,
        "pred": pred.label,
        "confidence": pred.confidence,
        "status": pred.status,
        "objects": pred.objects,
        "reasoning_sha256": pred.reasoning_sha256,
        "reasoning_chars": pred.reasoning_chars,
        "response_sha256": sha256_text(text) if text else None,
        "response_chars": len(text),
        "error": error,
        "latency_s": latency,
        "lat": latlon[0] if latlon else None,
        "lon": latlon[1] if latlon else None,
    }


# --------------------------------------------------------------------------
# Tile aggregation (H3 r9) of truth vs prediction
# --------------------------------------------------------------------------

def aggregate_h3(
    records: list[dict[str, Any]],
    classes: tuple[str, ...] = WILDFIRE_CLASSES,
    resolution: int = 9,
    min_cell_count: int = 3,
    location_source: str = "image EXIF GPS; images without GPS are not on this grid",
) -> list[dict[str, Any]]:
    """GeoJSON features: per cell, label histograms for truth and prediction
    and the agreement rate — never a per-image location. `location_source`
    names where the records' coordinates came from (EXIF by default; a
    dataset's own manifest for the matched sets) and is written into every
    cell's uncertainty block."""
    import h3

    cells: dict[str, dict[str, Any]] = {}
    for r in records:
        if r.get("lat") is None or r.get("lon") is None:
            continue
        cell = h3.latlng_to_cell(r["lat"], r["lon"], resolution)
        c = cells.setdefault(
            cell,
            {"n": 0, "n_scored": 0, "agree": 0, "truth": {}, "pred": {}, "unanswered": 0},
        )
        c["n"] += 1
        if r.get("truth"):
            c["truth"][r["truth"]] = c["truth"].get(r["truth"], 0) + 1
        if r["status"] == "ok":
            c["n_scored"] += 1
            c["pred"][r["pred"]] = c["pred"].get(r["pred"], 0) + 1
            if r["pred"] == r["truth"]:
                c["agree"] += 1
        else:
            c["unanswered"] += 1
    features = []
    for cell, c in sorted(cells.items()):
        boundary = h3.cell_to_boundary(cell)
        ring = [[lon, lat] for lat, lon in boundary] + [[boundary[0][1], boundary[0][0]]]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "h3_cell": cell,
                    "n_samples": c["n"],
                    "n_scored": c["n_scored"],
                    "labels_truth": dict(sorted(c["truth"].items())),
                    "labels_pred": dict(sorted(c["pred"].items())),
                    "agreement_rate": round(c["agree"] / c["n_scored"], 4) if c["n_scored"] else None,
                    "uncertainty": {
                        "model_derived": True,
                        "low_n": c["n"] < min_cell_count,
                        "n_unanswered": c["unanswered"],
                        "location_source": location_source,
                        "note": "zero-shot VLM predictions evaluated against dataset folder labels; supports no damage claim",
                    },
                },
            }
        )
    return features


def record_to_row(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False)


def prediction_dict(p: Prediction) -> dict[str, Any]:
    return asdict(p)
