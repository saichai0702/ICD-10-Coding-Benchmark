# ICD-10 Medical Coding Benchmarks (Harbor)

This repository holds two [Harbor](https://github.com/laude-institute/harbor) tasks in the
Terminal-Bench style. Both measure how well an LLM agent does **medical coding**: it reads
synthetic patient charts and assigns the billing codes a certified coder would.

The two tasks use the same 36 cases, the same grader and the same answer key. The only
difference is where the agent gets its coding reference material:

| Folder | Reference material | Network during the agent run | What it measures |
|---|---|---|---|
| [`medical-coding-rl/`](medical-coding-rl/) | FY2027 code sets are built into the container and searched with the `codetools` CLI | Harbor default | Coding skill when the reference books are provided |
| [`medical-coding-rl-internet-search/`](medical-coding-rl-internet-search/) | None. The agent has to find and download the code sets from the internet | `public` (web search and fetch allowed) | Coding skill plus the ability to find and use the right public sources |

Comparing a model's score on the two tasks shows how much of its performance comes from coding
knowledge and how much depends on having the correct reference data.

> [!IMPORTANT]
> **Raw CMS data is not in git. Download it with the setup script.**
>
> `medical-coding-rl/data/raw/` (326 MB of CMS zips and PDFs) is hosted on Google Drive as
> **`raw.zip`**. Running `./setup.sh` downloads it automatically with
> [`gdown`](https://github.com/wkentaro/gdown) and unpacks it into `medical-coding-rl/data/raw/`:
>
> ```bash
> ./setup.sh
> ```
>
> To fetch only the raw data:
>
> ```bash
> cd medical-coding-rl
> uv run --with gdown python scripts/download_raw.py
> ```
>
> **Backup link** (use it if the script can't download the file):
> **https://drive.google.com/file/d/1iPkcG5_32G3CTYEuiZi-OCIYVhgAJ1Uw/view?usp=sharing**
> Save the file as `medical-coding-rl/data/raw.zip` and run the command above again. The script
> unzips a `raw.zip` that is already there instead of downloading it.
>
> The raw data is only needed to **rebuild** the reference bundle (`scripts/build_reference.py`).
> The built bundle (`data/reference/`, `reference.tar.gz`) is already in the repo, so both
> benchmarks run without it.

---

## The ICD-10 coding task

The agent is a certified medical coder. Each of the 36 encounters lives in its own folder in the
container:

```
/app/cases/<CASE_ID>/
  chart/*.txt        provider documentation (H&P, progress notes, discharge summary, charge lines ...)
  encounter.json     care setting, claim type, dates, payer, code-set version
```

For every case the agent has to:

1. Read the chart and find the diagnoses and procedures the provider documented.
2. Assign codes from the public FY2027 code sets:
   - **ICD-10-CM** for diagnoses (principal / first-listed, secondary, external cause)
   - **ICD-10-PCS** for inpatient procedures
   - **HCPCS Level II** codes, modifiers and drug billing units
   - **Charge-master (CDM) lines** in place of CPT codes. CPT is AMA-licensed, so it is left
     out on purpose and any CPT code fails the case.
3. Follow the rules for the care setting. Inpatient claims need a principal diagnosis and POA
   (present-on-admission) indicators. Outpatient and professional claims use a first-listed
   diagnosis and no POA.
4. Give an evidence quote for each code, copied word for word from the chart.
5. Raise a **provider query** instead of guessing when the documentation is ambiguous (for
   example "urosepsis", which has no code).

All 36 claims go into one file, `/app/output/coded_claims.json`, with the case id as the key:

```json
{
  "ICD01-A": {
    "query_needed": false,
    "query_text": "",
    "codes": [
      {"code": "A41.51", "system": "ICD-10-CM", "role": "principal", "poa": "Y",
       "evidence": "exact words copied from this case's chart"}
    ]
  }
}
```

The cases come from the 10 worked examples in the *Medical Coding & Work-Type Playbook*
(ICD-01 … ICD-10), each combined with its "edge cases that change the answer": sepsis
sequencing, POA, laterality, drug-unit conversion, required provider queries, charge-master
lines and similar traps.

### Scoring

The grader is deterministic and uses no LLM judge. It runs in a separate, clean container, so
nothing the agent changes can affect it.

| Rule | Effect |
|---|---|
| Case missing from `coded_claims.json` | case reward 0 |
| Any invalid or non-billable FY2027 code, or any CPT/CDT code | case reward 0 |
| A provider query was required and the agent didn't raise one | case reward 0 |
| Each expected code: code 2, role 1, POA 1 (inpatient), modifiers 1 + units 1 (HCPCS/CDM) | points earned |
| Evidence quote not found word for word in the chart | −0.5 on that code |
| Extra unsupported code / known-wrong code / unnecessary query | −1 / −3 / −1 |

`case reward = earned / max`, clipped to 0..1. The **task reward is the mean over the 36 cases**.
With `SCORE_MODE=binary` the reward is 1 only when all 36 cases are fully correct.

---

## Folder 1: `medical-coding-rl/` (with reference data)

The agent container includes a bundle of the public FY2027 code sets (`reference.tar.gz`,
unpacked to `/opt/reference`) and a lookup CLI, `codetools`:

| Command | Contents |
|---|---|
| `codetools index`, `codetools eindex` | ICD-10-CM Alphabetic Index and External Cause Index |
| `codetools icd lookup\|search` | ICD-10-CM Tabular (notes, billable status) |
| `codetools pcs table\|lookup\|search` | ICD-10-PCS tables and codes |
| `codetools guidelines cm\|pcs <words>` | ICD-10-CM / PCS Official Guidelines |
| `codetools hcpcs`, `codetools modifier` | HCPCS Level II codes and modifiers |
| `codetools ptp`, `codetools mue` | NCCI edits (HCPCS Level II rows only) |
| `codetools lcd`, `codetools ncd` | Medicare LCD/NCD coverage policies |

All data comes from CMS and is public domain. Licensed content (CPT, CDT, AHA Coding Clinic) has
been removed. This folder also contains the source data (`data/`) and the build scripts that
produce the cases, the reference bundle and the answer key. See
[`medical-coding-rl/README.md`](medical-coding-rl/README.md) for details.

## Folder 2: `medical-coding-rl-internet-search/` (no reference data, internet search)

Same cases, same grader, but:

- **No reference bundle and no `codetools`** in the agent image. It ships `curl`, `wget`, `unzip`
  and `poppler-utils` (`pdftotext`) so the agent can download and unpack the CMS files itself.
  An empty `/app/reference/` folder is provided as a working directory.
- `task.toml` sets `network_mode = "public"` for the agent, which also keeps the agent's own web
  search and fetch tools turned on.
- The verifier still runs offline (`network_mode = "no-network"`) against a packaged list of
  valid codes.

This task tests whether the model can find the **correct version** of the code sets (FY2027
ICD-10-CM/PCS, HCPCS Level II October 2026) and apply them, rather than relying on what it
remembers.

---

## Setup with uv

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker (running), and an API key for the model
you want to test.

```bash
# 1. Install uv (skip if already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the repo
git clone https://github.com/saichai0702/ICD-10-Coding-Benchmark.git
cd ICD-10-Coding-Benchmark

# 3. One-step setup: uv sync in both folders + download raw.zip -> medical-coding-rl/data/raw/
./setup.sh

# 4. Check that it worked
cd medical-coding-rl && uv run harbor --version && cd ..
```

`setup.sh` options:

| Command | What it does |
|---|---|
| `./setup.sh` | `uv sync` in both folders (installs Python 3.12 and `harbor==0.25.0`), then downloads and unpacks `raw.zip` |
| `./setup.sh --skip-raw` | `uv sync` only, no raw data download |
| `./setup.sh --force` | Downloads `raw.zip` again and replaces `medical-coding-rl/data/raw/` |
| `./setup.sh --keep-zip` | Keeps `medical-coding-rl/data/raw.zip` after unpacking |

To set up by hand instead:

```bash
(cd medical-coding-rl && uv sync)
(cd medical-coding-rl-internet-search && uv sync)
(cd medical-coding-rl && uv run --with gdown python scripts/download_raw.py)
```

> [!TIP]
> If the download fails (Google Drive quota or a network error), open the
> [backup link](https://drive.google.com/file/d/1iPkcG5_32G3CTYEuiZi-OCIYVhgAJ1Uw/view?usp=sharing),
> save the file as `medical-coding-rl/data/raw.zip`, and run `./setup.sh` again.

Each folder has its own `pyproject.toml`, `uv.lock` and `.venv/`, so run commands from inside
the folder you're benchmarking. To use the environment without the `uv run` prefix, activate it
with `source .venv/bin/activate`.

### API keys

Put your keys in a `.env` file inside each benchmark folder. `.env` files are git-ignored.

```bash
# medical-coding-rl/.env  and  medical-coding-rl-internet-search/.env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...        # only if you benchmark OpenAI models / agents
```

Pass the file to Harbor with `--env-file .env`, or export it into your shell first:

```bash
set -a && source .env && set +a
```

---

## Running the benchmarks with Harbor

`scripts/run.sh` in each folder wraps `uv run harbor run -p tasks/medical-coding -y ...`. It
passes every argument through to Harbor and then writes `jobs/<job>/benchmark_report.md` and
`.csv`.

### 1. Sanity check with the oracle (should score 1.0, 36/36 cases)

```bash
cd medical-coding-rl
scripts/run.sh -a oracle --job-name oracle-reference

cd ../medical-coding-rl-internet-search
scripts/run.sh -a oracle --job-name oracle-internet
```

### 2. Benchmark a model WITH reference data

```bash
cd medical-coding-rl
scripts/run.sh -a claude-code -m anthropic/claude-opus-5-5 \
  --env-file .env --job-name reference-opus
```

### 3. Benchmark a model WITHOUT reference data (internet search)


```bash
cd medical-coding-rl-internet-search
scripts/run.sh -a <agent> -m <model provider>/ <model name> \
  --env-file .env --job-name internet-opus
```

### Calling Harbor directly (without the wrapper)

```bash
uv run harbor run -p tasks/medical-coding -a <agent> -m <model provider>/ <model name> \
  --env-file .env --job-name my-run -y
uv run python scripts/job_report.py jobs/my-run      # write the benchmark report
```

### Useful options

| Option | Purpose |
|---|---|
| `-a <agent>` | Agent harness: `claude-code`, `codex`, `gemini-cli`, `openhands`, `terminus-2`, `oracle`, ... (`uv run harbor run --help` lists all of them) |
| `-m <provider/model>` | Model, for example `anthropic/claude-opus-5-5`, `anthropic/claude-sonnet-5-5`, `openai/<model>`. Repeat it to run several models |
| `-k <n>` | Attempts per trial (e.g. `-k 3` for pass@k / variance) |
| `-n <n>` | Concurrent trials (default 4) |
| `--effort <level>` | Reasoning effort, for agents that support it |
| `--job-name <name>` | Output folder name under `jobs/` |
| `--env-file .env` | Load API keys |

Examples:

```bash
# Three attempts of Sonnet on the reference task
scripts/run.sh -a claude-code -m anthropic/claude-sonnet-5-5 -k 3 --env-file .env

# Two models on the internet-search task in one job
scripts/run.sh -a claude-code -m anthropic/claude-opus-5-5 -m anthropic/claude-sonnet-5-5 --env-file .env
```

### Reading the results

```bash
uv run harbor view jobs                       # browse trajectories in the Harbor viewer
cat jobs/<job>/benchmark_report.md            # summary written by scripts/run.sh
```

Each trial writes the following to `jobs/<job>/<trial>/verifier/`:

- `reward.txt`: the task reward (0..1)
- `reward-details.json`: per-case scores
- `report.md` / `report.json`: expected vs submitted codes for each case
- `coded_claims.json`: a copy of the agent's answer

To compare a model across the two settings, run it on both tasks and compare the `reward.txt`
values (or the two `benchmark_report.md` files).

---

## Repository layout

```
.
├── README.md                              this file
├── setup.sh                               uv sync both folders + download raw.zip
├── medical-coding-rl/                     benchmark WITH reference data
│   ├── tasks/medical-coding/              the Harbor task
│   │   ├── instruction.md                 prompt given to the agent
│   │   ├── task.toml                      timeouts, resources, verifier settings
│   │   ├── environment/                   Dockerfile, codetools.py, reference.tar.gz, cases/
│   │   ├── solution/                      oracle + groundtruth.json (uploaded only for -a oracle)
│   │   └── tests/                         grader: score.py, report.py, groundtruth.json, valid codes
│   ├── data/                              source cases + CMS reference data
│   │   └── raw/                           NOT in git: downloaded by setup.sh (raw.zip)
│   ├── scripts/                           run.sh, download_raw.py, job_report.py, build_*.py, selftest.py
│   └── pyproject.toml / uv.lock
└── medical-coding-rl-internet-search/     benchmark WITHOUT reference data (internet search)
    ├── tasks/medical-coding/              same layout; no codetools, network_mode = "public"
    ├── scripts/
    └── pyproject.toml / uv.lock
```

To rebuild cases or reference data, or to run the Docker-free self-test, see the
**Build and test** section of [`medical-coding-rl/README.md`](medical-coding-rl/README.md).
