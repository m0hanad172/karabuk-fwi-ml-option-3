# OLD_PROJECT_NOTES.md

## Purpose
This file explains how the old project should be used as a reference during migration into the new clean project.

The old project is:
- a reference implementation
- a source of reusable assets
- not the final architecture

Do NOT continue the old prototype blindly.
Use it only to migrate correct logic and validated assets.

---

## Old Project Role
The old project should be used for:
- understanding existing logic
- reusing validated feature engineering
- reusing validated data fetching logic
- reusing the processed dataset
- reusing baseline evaluation results as reference

The old project should NOT define the final architecture.

---

## Key Assets to Reuse
### 1) Dataset
Reuse:
- processed final dataset used in the current prototype

Purpose:
- baseline training/evaluation reference
- migration input for the new project

### 2) Feature schema
Reuse:
- the final feature schema
- training feature names
- feature grouping philosophy

Purpose:
- maintain training/inference consistency

### 3) Feature engineering logic
Reuse:
- rolling features
- EWMA features
- VPD / HDW / fuel drying rate
- seasonal encodings
- dryness features

Purpose:
- preserve the strongest validated technical asset from the old project

### 4) Weather data fetching logic
Reuse/adapt:
- Open-Meteo weather fetching logic
- history-window building logic
- raw input extraction logic

### 5) Soil moisture logic
Reuse/adapt:
- soil moisture resolving logic
- fallback logic if needed

### 6) Baseline metrics and findings
Reuse as reference:
- current regression results
- current classifier results
- current threshold as baseline only
- previous evaluation outputs and plots

---

## What Must Be Changed in the New Project
### 1) Architecture
Change from:
- parallel regressor + classifier

To:
- Option 3 stacked architecture

### 2) Decision logic
Change from:
- mostly classifier-centered decision behavior

To:
- regression-centered decision with classifier support

### 3) Frontend
Replace:
- old Streamlit dashboard

With:
- professional React / Next.js frontend

### 4) Backend structure
Refactor:
- prototype scripts
- routes
- inference flow
- run history logic

Into:
- clean modular backend

### 5) History / audit
Unify:
- run history
- audit outputs
- decision traces

Into:
- single structured source of truth

---

## What Should Be Discarded or Ignored
The following parts of the old project should NOT be treated as final architecture:

- old Streamlit dashboard as a product UI
- prototype-specific run scripts if redundant
- stale or duplicated artifacts
- confusing parallel model logic
- prototype shortcuts that break architectural clarity

---

## What Claude Code Should Do First
Before coding:
1. inspect the old project only as a reference
2. identify reusable assets
3. identify prototype mistakes not to migrate
4. propose a clean migration plan into the new project

Only after that:
- begin implementation in the new workspace

---

## Important Rule
The old project is valuable because it already contains:
- data
- feature logic
- baseline results
- weather integration logic

But the new project must be:
- cleaner
- more coherent
- more professional
- more aligned with Option 3

Do not simply extend the old project structure.