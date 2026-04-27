# PROJECT_BRIEF.md

## Project Name
Karabuk Wildfire Risk Prediction System — Option 3 Stacked Architecture

## Project Scope
This project is for **Karabük, Turkey** (Karabük city / operational scope), focused on **wildfire risk prediction** during the fire season.

### Time scope
- Historical data: **2012–2025**
- Fire season only: **May to October**

---

## Core Project Identity
This project is a **machine-learning surrogate system for FWI-style wildfire danger estimation**.

The real core contribution is:

> Build a machine-learning system that can estimate daily fire-weather danger (FWI-like risk) from easy-to-fetch live-compatible weather features and engineered temporal-memory features, without requiring the full complex Canadian FWI equation chain at runtime.

This project is **NOT**:
- a generic wildfire image detection project
- a computer vision fire/smoke system
- a satellite-heavy redesign
- a full official-anchor/state-equation runtime system as the core contribution

---

## Practical Motivation
The system is designed for **safety-first operational use**.

Important assumption:
- missing a dangerous day is worse than doing extra checking
- false positives are more acceptable than false negatives

---

## Feature Philosophy
Only use features that are:
- directly available from weather APIs
- or easily engineered locally from them
- realistic for live deployment
- not dependent on complex official FWI runtime equations

### Direct/API features
- temperature
- relative humidity
- wind speed
- precipitation
- cloud cover
- shortwave radiation
- ET0 evapotranspiration
- soil moisture 0–7 cm mean

### Engineered features
- cyclical seasonal encoding
- VPD
- HDW
- fuel drying rate
- dew point
- rolling rainfall / humidity / temperature / wind memory
- EWMA memory features
- dry-day features

### Final schema
Current final schema uses **35 training features** in the old project, but one duplicate feature should be removed during rebuild if confirmed (`days_since_last_rain` vs `consecutive_dry_days`).

---

## Old Project Status
The old project is a late prototype / early operational MVP.

It already contains:
- processed dataset
- feature schema
- feature engineering logic
- weather fetching
- soil moisture fallback logic
- ML training pipeline
- live inference
- API layer
- Streamlit dashboard
- run history
- drone logic draft
- notebooks and baseline metrics

The old project should be treated as:
- **reference implementation**
- **asset source**
- **migration source**

The old project should **NOT** be treated as the final architecture.

---

## Chosen New Direction
The new project must be built around **Option 3 (stacked architecture)**.

### Stage 1 — Regression backbone
Input:
- full final training feature vector

Output:
- `predicted_fwi`

Purpose:
- this is the core scientific model of the project

### Stage 2 — Safety support layer
Input:
- `predicted_fwi`
- plus a small selected set of support features

Output:
- `high_risk_probability`

Purpose:
- support the operational decision, especially near the threshold
- compensate for regression underestimation in the dangerous tail

### Final decision philosophy
The final decision must remain centered on **predicted_fwi**, with the classifier acting only as a support layer near the threshold.

Example final logic:
- if `predicted_fwi >= 35` → High Risk
- else if `predicted_fwi` is near threshold and `high_risk_probability` is high → High Risk
- else → not High Risk

This means:
- regression stays the core
- classifier does not “steal” the project identity

---

## Important Technical Constraint
Stage 2 must be trained correctly using **out-of-fold predictions from Stage 1**.
Do not use naive in-sample regression predictions for stacking.

Use:
- walk-forward validation
- temporal folds
- OOF predictions
- no leakage

---

## Operational Logic
### Live weather
- display-only
- update every 5 minutes or via refresh button
- must be strictly separated from model input data

### Scheduled model runs
- main run at **11:00**
- optional re-check at **15:00**

### Manual checks
- available from dashboard
- must run the model pipeline
- must NOT simply reuse the live weather cards

### Drone logic
- separate operational layer
- if high-risk flag is active, drone checks may happen every 30 minutes
- do not hardwire drone logic inside the ML model itself

---

## Live Weather Philosophy
There must be a strict separation between:

### Live Display Layer
- current weather cards
- source timestamp
- dashboard fetch time
- display-only
- can use a trusted local Karabük weather source

### Model Input Layer
- used for scheduled/manual model runs
- must remain consistent with the model pipeline and training logic

Do not mix these two layers.

---

## UI / Frontend Requirements
Use a professional frontend, preferably:
- React + TypeScript
- Next.js
- Tailwind CSS
- shadcn/ui
- charting with Recharts or equivalent

### Required tabs / sections
#### Tab 1 — Live Overview
- current weather
- latest source snapshot
- dashboard fetch time
- latest model result
- alert status
- next scheduled run

#### Tab 2 — Risk Decision
- predicted_fwi
- high_risk_probability
- high_risk_flag
- decision explanation
- manual check controls

#### Tab 3 — Features / Inputs
- raw inputs used in latest model run
- engineered features used in latest model run
- Stage 2 meta features
- feature validation status

#### Tab 4 — Historical Analytics
- compare with previous years
- FWI trends
- seasonal comparisons
- high-risk history
- charts and analytics

#### Tab 5 — Run History / Audit
- scheduled/manual runs
- timestamps
- outputs
- decisions
- traceability

#### Tab 6 — System / Model
- model version
- threshold
- source adapters
- health status
- data quality warnings

#### Tab 7 — Monitoring / Drone
- drone status
- camera/drone feed placeholders
- ready-to-connect UI structure for future stream integration
- disconnected/loading/no-signal states

---

## Drone Camera Requirement
I want the frontend architecture to include:
- placeholder video frames/cards
- labels such as:
  - Drone Camera Feed
  - Area Monitoring Feed
- loading / disconnected / no signal states

Important:
- do NOT build full video analytics now
- only prepare the UI structure and backend contract for future stream integration

---

## Backend Requirements
Use:
- FastAPI
- clear modular backend
- proper separation of:
  - routes
  - services
  - feature building
  - weather/source adapters
  - model inference
  - decision logic
  - scheduling
  - run history / audit
  - validation

Prefer a clean new architecture rather than prototype patching.

---

## Data / Storage Requirements
Prefer a more structured system than scattered flat files.

Suggested:
- SQLite or PostgreSQL for run history / config / audit
- filesystem for model artifacts
- CSV/processed dataset as source data

---

## What Should Be Reused from the Old Project
Reuse or adapt:
- processed dataset
- feature schema
- feature engineering logic
- Open-Meteo fetching logic
- soil moisture resolver logic
- notebooks as reference only
- baseline metrics / plots as reference only

---

## What Should Not Be Carried Forward Blindly
Do not carry forward prototype problems such as:
- the old parallel architecture
- broken API patterns
- stale files / duplicated artifacts
- confusing dashboard logic
- messy run-history duplication
- old Streamlit assumptions

---

## Implementation Priority
### Phase 1 — ML Core First
This is the most important phase.

Implement first:
- Stage 1 regression
- walk-forward CV
- OOF prediction generation
- Stage 2 stacked classifier
- final decision rule
- full stacked evaluation

Only after Phase 1 is validated:
- move to API
- then frontend
- then operational polish

### Important principle
The project lives or dies in **Phase 1**, not in frontend polish.

---

## What Success Means
A successful rebuild should produce:
- a clean and professional codebase
- a stacked Option 3 pipeline
- regression as the real core model
- classifier as a support layer
- a clear operational dashboard
- strong academic framing
- a system that is easier to defend and explain than the current prototype

---

## Final Rule
Do not start by coding blindly.

First:
1. understand the project exactly
2. propose the clean architecture
3. propose the migration plan
4. confirm what will be reused and what will be discarded
5. then implement phase-by-phase