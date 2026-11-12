# Medical coding RL environment (FY2027, license-clean)

One Harbor task (same layout as Terminal-Bench's `medical-claims-processing`) with 36 cases
(data points) built from the *Medical Coding & Work-Type Playbook*: the 10 worked examples
(ICD-01 … ICD-10) × their "edge cases that change the answer". The agent codes all 36 encounters
in one trial; the verifier compares its answers with one ground-truth file keyed by case id.

## Quick start

```bash
uv sync                                                     # installs harbor (pinned in pyproject.toml)
scripts/run.sh -a oracle                                    # sanity check: reward 1.0, 36/36 cases
scripts/run.sh -a claude-code -m anthropic/claude-opus-5-5  # benchmark an agent
uv run harbor view jobs                                     # browse trajectories
```

`scripts/run.sh` runs `uv run harbor run -p tasks/medical-coding` (extra arguments go to Harbor),
then writes `jobs/<job>/benchmark_report.md` and `.csv`.

## Layout

```
tasks/medical-coding/            THE Harbor task
  instruction.md                 what the agent is told
  task.toml                      metadata, timeouts, separate verifier, /app/output artifact
  environment/                   agent container
    Dockerfile  codetools.py  reference.tar.gz
    cases/<ID>/chart/*.txt  encounter.json      the 36 data points -> /app/cases/<ID>/
  solution/                      oracle (uploaded only for `-a oracle`)
    groundtruth.json             {case_id: expected output + scoring info}, all 36 cases
    solve.sh  oracle.py          writes groundtruth outputs to /app/output/coded_claims.json
  tests/                         verifier (uploaded only at grading time)
    test.sh                      score.py -> report.py
    score.py                     compares coded_claims.json with groundtruth.json case by case
    report.py                    schema check + per-case expected vs submitted -> report.md / .json
    output_schema.json           JSON Schema for /app/output/coded_claims.json
    groundtruth.json             identical copy of solution/groundtruth.json (see below)
    valid_codes.json.gz
data/                            sources: cases.py (charts + answers), reference/, raw/
scripts/                         build_cases.py, selftest.py, run.sh, job_report.py, build_reference.py
```

**groundtruth.json** has the case id as the key and that case's expected output as the value:

```json
{
  "ICD10-A": {
    "query_needed": false,
    "query_text": "",
    "codes": [{"code": "J3301", "system": "HCPCS", "role": "line", "modifiers": ["JZ"], "units": 4,
               "evidence": "Triamcinolone acetonide 40 mg"}, "..."],
    "scoring": {"optional": [], "forbidden": ["M17.12", "M17.0"], "cdm_lines": ["INJ1"]},
    "meta": {"title": "...", "playbook_example": "ICD-10", "setting": "office", "edge_case_tags": ["..."]}
  }
}
```

`query_needed`, `query_text` and `codes` are exactly what the agent must write for that case.
`scoring`, `meta`, and the per-code `accept` (equally correct alternatives) and `role_scored`
(`false` = sequencing not graded) are used only by the grader.

**Why two copies:** Harbor uploads `solution/` only when the oracle agent runs. When a real agent is
graded, the verifier sees only `tests/`. `scripts/build_cases.py` writes both files from
`data/cases.py`, byte for byte identical. Never edit either by hand.

Each trial writes `reward.txt`, `reward-details.json`, `report.md`, `report.json` and a copy of the
agent's `coded_claims.json` to `jobs/<job>/<trial>/verifier/`.

## Like you're 10

The agent gets a made-up patient chart and public code books it can search. It writes down the
codes that go on the bill. A teacher with a secret answer sheet checks every code. Tricks are
hidden in each chart: the patient got sick *after* arriving, a word with no code ("urosepsis")
that means you must ask the doctor, a drug dose that must be turned into billing units.
Right codes earn points; made-up codes lose points; guessing when you should have asked scores 0.

## As a function

```
trial(agent) -> /app/output/coded_claims.json = {case_id: claim}   (36 cases)

  inputs:  /app/cases/<ID>/chart/*.txt       synthetic chart (+ charge_lines.txt for charge-master lines)
           /app/cases/<ID>/encounter.json    setting, dates, payer, code-set version
           codetools                 public lookup only: Index, Tabular, PCS tables, Guidelines,
                                     HCPCS Level II, NCCI (Level II), LCD/NCD, POA-exempt list
  agent:   read chart -> Index -> Tabular -> guidelines -> edits/coverage -> query if unclear
  claim:   {query_needed, query_text, codes:[{code, system, role, poa, modifiers, units, evidence}]}

case reward = verifier(claim, groundtruth[case_id] + pristine chart + valid-code list) -> 0..1
reward      = mean of the 36 case rewards
```

## License rule: no licensed content anywhere

| Licensed material | Where it would have appeared | What we do |
|---|---|---|
| CPT codes, descriptors, modifiers 25/59 (AMA) | NCCI/MUE files, LCD articles, HCPCS text, playbook ICD-08/09/10 | Removed from the bundle; never in charts, gold or answers |
| CDT dental codes (ADA) | HCPCS D-codes | Excluded |
| AHA Coding Clinic | Hard-case advice | Not used |

- Services that would carry a CPT code appear as **charge-master lines** (`PROC1`, `LAB1`, `INJ1`)
  with a plain-language description written by us. The agent reports only the public parts:
  HCPCS Level II modifiers (PT, GA/GZ, RT/LT), units, or a HCPCS Level II replacement (G0121).
- The scorer **fails any answer that contains a CPT code** (`system: "CPT"` is never valid).
- `scripts/build_reference.py` and `scripts/build_cases.py` both audit for CPT-pattern codes and stop if any leak.

## Reference bundle (`data/reference/`, built by `scripts/build_reference.py`)

| Dataset | Version | Source | License |
|---|---|---|---|
| ICD-10-CM codes, Tabular, **Alphabetic Index**, External Cause Index | FY2027 | cms.gov | Public domain |
| ICD-10-PCS codes + tables | FY2027 | cms.gov | Public domain |
| ICD-10-CM and ICD-10-PCS Official Guidelines (text) | FY2027 | cms.gov | Public domain |
| POA exempt list | FY2027 | cms.gov | Public domain |
| HCPCS Level II codes + modifiers (D-codes excluded) | October 2026 | cms.gov | Public domain |
| NCCI MUE + PTP, HCPCS Level II rows only | 2026 Q3 | local CMS copy | CPT rows removed |
| LCD/NCD: policy text (CPT numbers redacted) + ICD-10 coverage lists | MCD snapshot | local CMS copy | CPT content removed |

Downloaded but **not yet wired in**: MS-DRG v44 Java grouper + definitions manual (`data/raw/fy2027/`).

## Scoring (`tests/score.py`, deterministic, no LLM)

| Rule | Effect |
|---|---|
| Case missing from `coded_claims.json` | case reward 0 |
| Any code invalid/non-billable in FY2027, or any CPT/CDT code | case reward 0 |
| Ground truth says "query the provider" and agent didn't query | case reward 0 |
| Per expected code: code 2, role 1, POA 1 (inpatient), modifiers 1 + units 1 (HCPCS/CDM lines) | points |
| Evidence quote not found word for word in the chart | −0.5 on that code |
| Extra unsupported code / known-wrong code / needless query | −1 / −3 / −1 |

`case reward = earned / max`, clipped to 0..1. Task reward = mean over the 36 cases
(`SCORE_MODE=binary`: 1 only if all 36 cases are fully correct).

The verifier runs in a fresh container built from `environment/` (`verifier.environment_mode =
"separate"`), so the evidence check uses pristine charts and nothing the agent changed can affect
grading; Harbor copies `/app/output` into it as an artifact. `report.py` also validates the file against
`output_schema.json`; schema problems are reported but do not change the reward.

## Build and test

```bash
python scripts/build_reference.py        # data/reference/ from data/raw/fy2027 + local CMS copies
python scripts/build_cases.py            # data/cases.py -> environment/cases/, groundtruth.json (x2), audits
python scripts/selftest.py               # no Docker: oracle = 1.0 on all 36; landmine mutants < 1.0
uv run harbor lint tasks/medical-coding  # Harbor static checks
scripts/run.sh -a oracle                 # end to end in Docker
```

To change a chart or an answer, edit `data/cases.py` and rerun `build_cases.py`. To change the
grader, report, Dockerfile, instruction or task config, edit the file in `tasks/medical-coding/`.

## Known limits

- **Gold needs CCS/CPC sign-off** (`meta.gold_review_status` in `groundtruth.json`).
- **W18.09XA vs W01.0XXA (ICD-04):** the FY2027 External Cause Index sends "tripping over rug,
  with fall" to W18.09; the playbook says W01.0XXA. Gold uses W18.09XA and accepts W01.0XXA
  until a coder decides.
- **Lost with CPT:** NCCI bundling between CPT codes (ultrasound guidance into joint injection),
  modifier 25, and CPT procedure selection are no longer tested.
- **NCCI is 2026 Q3**; the Q4 files sit behind the AMA license click-through on cms.gov.
- DRG is not scored (grouper not wired in); diagnosis pointers are not scored.
