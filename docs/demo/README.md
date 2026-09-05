# Demo video

`record_demo.py` produces the three-minute demo submitted to OASIS Track A. It is a
scripted, genuine walk-through — nothing is mocked:

| scene | what is shown | source of what appears |
|---|---|---|
| Landing page | the public site | `https://rayford295.github.io/ray-resilience/` |
| Resident mode | an address is looked up and receives one of three answers (covered / outside / not determined) | the app served locally from the committed artifacts; geocoding by the US Census geocoder, falling back to OpenStreetMap Nominatim |
| Planner mode | the Damage × SVI priority layer, the trade-off slider re-ranking tiles (every move audit-logged), lineage back to hashed source snapshots | committed `events/eaton-2025/` artifacts |
| Ask Ray | a question the policy refuses before any model call (the refusal names the rule), then two grounded answers with an artifact citation on every sentence | the local gateway (`uvicorn gateway.main:app`) over Ollama (`gpt-oss:20b`), policy `src/geosteward/harness/policy_v1.yaml` |

Each scene is recorded in real time with Playwright (1280×720). Post-processing only
speeds up waiting (title cards say by how much), then concatenates. The `out/` directory
is git-ignored; the final `ray-resilience-demo.mp4` is published outside the repository.

```bash
uvicorn gateway.main:app --port 8080            # Ollama serving gpt-oss:20b
cd app && npm run dev -- --port 5173            # the PWA
python -m pip install playwright imageio-ffmpeg && python -m playwright install chromium
python docs/demo/record_demo.py --out docs/demo/out
```

While the repository was private, the Tier-1 live watch badge in the recording reads
"live watch unavailable — no nationwide layer shown (declared, not faked)": the app
fetches the `live-data` branch, which was not yet publicly readable. That is the
degradation the design specifies, shown as it happened.
