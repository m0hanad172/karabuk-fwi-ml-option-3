# CORE_IDEA

The final project in two parts: the theoretical idea, and the technical
architecture that realises it.

---

## A) Theoretical idea

### What this project is

An operational wildfire risk console for **Karabük, Turkey**. It runs
twice daily, at **11:00** and **15:00 Europe/Istanbul**, and produces a
single actionable decision: *is tomorrow a high-risk day?* The UI surfaces
that decision to operators together with the supporting evidence (predicted
FWI, Stage 2 probability, feature inputs, last scheduled runs, and a
read-only drone launch policy derived from the decision).

The system also ships a motivation tab ("Impact & Context") and a
detection layer (drone / webcam / PC camera MJPEG feeds) that share the UI
but are strictly isolated from the prediction pipeline.

### Why we built it

Karabük's 2025 fire season produced real, measurable harm — 1,839 evacuated
people, 19 evacuated villages, roughly 55 hectares of forest damaged in
the Burunsuz incident, and a five-day major suppression window. Reactive
response is expensive and unsafe. A decision-support signal that arrives
hours earlier (and is stable, interpretable, and auditable) meaningfully
shifts operational posture: stage resources earlier, pre-notify villages,
pre-stage aircraft, etc. That shift is the entire motivation for the
system.

### Why we do NOT rely on the full Canadian FWI runtime equation chain

The canonical Canadian Forest Fire Weather Index is a cascade of physical
sub-indices (FFMC → DMC → DC → ISI → BUI → FWI), each requiring carefully
initialised state carried forward from day to day, several lookup tables,
and strict assumptions about noon observations. In a live operational
setting this chain has three structural problems for us:

1. **State fragility.** A single missing day, a timezone slip, or a gap
   in noon data silently corrupts the carried state for every subsequent
   day, so any small data-feed hiccup bleeds into tomorrow's output.
2. **No learning headroom.** The equations are fixed. They cannot adapt
   to Karabük's micro-climate (inland Black Sea transition, Safranbolu
   humidity regime, soil-moisture driven fuel drying) without an
   orthogonal correction layer on top — which is effectively an ML model.
3. **Operational brittleness.** Reproducing the full chain from Open-Meteo
   archive + forecast data requires resolving ambiguities that the
   canonical equations assume away (e.g. "noon temperature" under a
   daily-aggregated API). We have already seen the old legacy
   implementation drift for exactly this reason.

We therefore treat the canonical FWI as the *ground-truth label* on the
2012–2025 historical record and learn a **direct regressor** that maps
current weather + engineered features → FWI, rather than reassembling the
cascade at runtime.

### Why Option 3 is the chosen design

Three options were compared end-to-end:

- **Option 1 (regression only)** — one HistGBR that predicts FWI. Cheap
  and stable, but underperforms on the rare high-risk tail because the
  regression loss is dominated by the non-risky mass of the distribution.
- **Option 2 (parallel classifier)** — a separate classifier trained
  directly on the same raw features. It has no knowledge of the
  regressor's internal signal, so the two heads disagree in the grey zone
  and the final rule becomes ad-hoc.
- **Option 3 (stacked)** — Stage 1 HistGBR regresses FWI, and Stage 2 is
  a RandomForest **safety classifier** trained on Stage 1's out-of-fold
  predictions plus three supporting features (`rh`, `ws`,
  `fuel_drying_rate`). Stage 2 exists only to rescue borderline days in
  the "grey zone" (28 ≤ predicted FWI < 35) that Stage 1 would otherwise
  mark normal. Option 3 beat Option 2 on the 2025 holdout (6 vs. 8
  missed high-risk days) while staying interpretable and tunable.

### Why safety-first matters

A false-positive (predict high risk on a normal day) costs logistics. A
false-negative (miss a real high-risk day) potentially costs lives,
forest, and the village evacuations we already saw in 2025. The stacked
decision rule is therefore asymmetric on purpose: Stage 1's regression
defines the primary decision, Stage 2's classifier exists *only* to pull
borderline days into the HIGH_RISK bucket, and the probability threshold
is tuned to err toward "stage the response earlier." Safety is a product
requirement, not a modelling preference.

---

## B) Technical architecture

### Scope

- **Geography:** Karabük, Turkey (lat 41.2061, lon 32.6204).
- **Operational timezone:** Europe/Istanbul (TRT). Every stored and
  displayed timestamp is tz-aware Istanbul ISO 8601, enforced by a single
  helper module `src/api/time_utils.py`.
- **Data window:** 2012 → 2025, **May – October** only (the fire season).
  Winter data is deliberately excluded from training so the model does
  not learn dormant-season patterns that dilute fire-season signal.

### Data pipeline

- **Weather source:** Open-Meteo.
  - `archive-api.open-meteo.com` for historical (training) data.
  - `api.open-meteo.com` for forecast (live model input).
  - The cutover date is computed in **Istanbul-local time** so runs near
    midnight pick the correct source.
- **Soil moisture:** Open-Meteo soil-moisture layers with a daily-mean
  resolver (`soil_moisture_0_to_7cm_mean`) and an hourly-layer fallback
  for days where the daily variable is missing.
- **Feature engineering:** 34 engineered training features including
  rolling means, EWMA deltas, and a `fuel_drying_rate` signal derived
  from RH trajectory. Feature schema is locked in
  `src/features/feature_schema.py` and validated per-run before Stage 1
  is invoked.

### Stage 1 — regression backbone

- **Model:** `HistGradientBoostingRegressor` (scikit-learn).
- **Target:** canonical FWI label from the historical archive.
- **Validation:** **walk-forward** — first fold trains 2012–2015 and
  predicts 2016, next fold trains 2012–2016 and predicts 2017, and so on
  through 2025. This produces out-of-fold predictions that Stage 2 uses
  as input.
- **Holdout metric:** R² ≈ 0.819 on the 2025 fire-season holdout.
- **Outputs:** `predicted_fwi` (float, continuous).

### Stage 2 — safety classifier

- **Model:** `RandomForestClassifier` (stacked).
- **Inputs:** Stage 1's out-of-fold `predicted_fwi` plus three support
  features: `rh`, `ws`, `fuel_drying_rate`.
- **Target:** binary `target_ge_35` (FWI ≥ 35).
- **Role:** **rescue**, not override. Stage 2 only promotes days where
  Stage 1's predicted FWI lies in the grey zone `[28, 35)` and Stage 2's
  probability ≥ `DEFAULT_PROBABILITY_THRESHOLD` (0.10). It never
  *demotes* a day Stage 1 already marked high.

### Final decision rule

```
if predicted_fwi >= CLASS_THRESHOLD (35):
    decision = HIGH_RISK                        # Stage 1 says so directly
elif predicted_fwi >= NEAR_THRESHOLD (28) and
     stage2_probability >= PROB_THRESHOLD (0.10):
    decision = HIGH_RISK                        # Stage 2 rescue
else:
    decision = NORMAL
```

The rule is expressed as a single function (`predict_from_features`) so
the decision reason can be rendered literally in the UI ("Stage 1 above
threshold" / "Stage 2 rescue in grey zone" / "Below risk zone").

### Operational runs: 11:00 and 15:00 Istanbul

- **Scheduler:** APScheduler `BackgroundScheduler` pinned to
  `ZoneInfo("Europe/Istanbul")`.
- **Jobs:** two `CronTrigger(hour=11)` and `CronTrigger(hour=15)` jobs,
  both tagged `run_type="scheduled"`.
- **Why two slots:** the morning run catches the overnight forecast
  update; the afternoon run catches any correction before the high-risk
  late-afternoon window. Both are always registered so the Scheduler card
  always shows both next-run times.

### Manual checks

- Operators can trigger a full pipeline run from the Risk Decision tab
  or via `POST /risk/check`.
- `run_type="manual"`, which means the run IS eligible to influence the
  drone policy if `allow_drone_trigger=true` is passed.
- Manual runs use **fresh model-input weather** — they do NOT reuse the
  live display weather cards (see below).

### Live display weather vs. model input — strict separation

- **Live display weather** (`/weather/live`) uses
  `open-meteo.com/v1/forecast` with the current variable set and is shown
  only on the Overview tab's Weather panel. It is clearly labelled
  "Display Only."
- **Model input weather** uses daily aggregates + soil moisture via a
  different code path (`src/data/fetch_weather.py`,
  `src/data/soil_moisture.py`) and only ever lands inside the pipeline.
- The two paths never share a cache, never share a fetch, and the live
  display values are never fed into the model. This is enforced by
  module boundary.

### Monitoring / detection layer — strict separation

- The detection layer (`src/monitoring/*`, `/monitoring/*` routes) hosts
  three MJPEG feeds (drone, webcam, PC camera) and a YOLO-style
  fire-detector that writes a ring buffer of notifications.
- It is **forbidden** from importing `src.inference`, `src.pipeline`,
  `src.models.stage1/2`, or `src.api.db.database`. This is an
  architectural guard, not a convention.
- Detection events never touch `run_history` and never modify
  `predicted_fwi`. They only:
  1. append to the notifications ring buffer, and
  2. show up on the Monitoring tab.
- The drone launch *policy* on the Monitoring tab is the output of the
  Option 3 pipeline (`/drone/state`), not of the detection layer. The
  detection layer reuses the drone hardware for *observation* when the
  policy is active; it does not decide when the drone flies.

### Why the old legacy FWI model is not used

The pre-Option-3 implementation tried to reassemble the Canadian FWI
cascade at runtime from Open-Meteo data. It was retained for reference
but is not part of the operational path:

- It had state-drift issues across day boundaries (see §A above).
- It could not be tuned for the Karabük micro-climate without adding an
  ML correction layer, at which point we would be doing Option 3 anyway.
- It did not expose a calibrated probability, so Stage-2-style rescue of
  grey-zone days was not possible.
- We still import the canonical labels from the archive for training —
  so the canonical FWI equation is the teacher, but not the runtime.

### Why legacy camera/drone detection assets are reused (monitoring only)

The previous project invested in working MJPEG plumbing for the DJI Tello
drone and two OpenCV camera indexes. Those feeds are genuinely useful as
an *observation* layer for the operator during an active alert window.
We reuse them for exactly that purpose — and nothing else. They live
under `src/monitoring/` with no import path back into the prediction
pipeline, they never write `run_history`, and the dashboard labels the
whole page "Detection Layer — Fire detection only — never writes
predicted_fwi" to make the contract visible on screen.

---

## Operational invariants (the contract)

These are the properties every change to the system must preserve:

1. Two scheduled operational slots per day: **11:00** and **15:00
   Europe/Istanbul**, always both visible on the Scheduler card.
2. Only `run_type ∈ {manual, scheduled}` can appear as the Latest
   Operational Run on Overview or influence the drone policy.
3. Every timestamp that crosses the API boundary is a tz-aware Istanbul
   ISO 8601 string produced by `src/api/time_utils.py` — no naive
   datetimes, ever.
4. The prediction pipeline and the detection layer do not share any
   write path into `run_history` or `system_state`.
5. Live display weather is never used as model input.
