You are a certified medical coder. Code the encounter documented in `/app/chart/`:
{{SETTING}}.

The care setting, claim type, dates, payer and code-set version are in `/app/encounter.json`.
Apply the coding rules for that setting (inpatient: principal diagnosis and POA indicators;
outpatient and professional: first-listed diagnosis, no POA).

## Reference desk

Run `codetools --help`. It is a lookup tool for public code sets only. It never contains the
answer for a chart.

- ICD-10-CM: Alphabetic Index (`codetools index`), External Cause Index (`codetools eindex`),
  and Tabular (`codetools icd lookup|search`)
- ICD-10-PCS tables and codes (`codetools pcs table|lookup|search`)
- ICD-10-CM and ICD-10-PCS Official Guidelines (`codetools guidelines cm|pcs <words>`)
- HCPCS Level II codes and modifiers (`codetools hcpcs`, `codetools modifier`)
- NCCI PTP and MUE edits, HCPCS Level II rows only (`codetools ptp`, `codetools mue`)
- Medicare LCD/NCD policies and coverage lists (`codetools lcd`, `codetools ncd`)

All code sets are FY2027 (HCPCS Level II October 2026). Run `codetools versions` to confirm.
Look terms up in the Index first, then verify the code in the Tabular, including its notes
and whether it is billable. Code only from provider documentation, not from lab values or
nursing notes alone.

## Charge-master lines (no CPT)

Some services are listed in `/app/chart/charge_lines.txt` as hospital charge-master lines
(for example `PROC1`, `LAB1`, `INJ1`). Their procedure codes come from the charge master and are
not part of this task. **Never write a CPT or CDT code.** Any CPT/CDT code makes the whole
answer invalid.

- Report each charge-master line with `"system": "CDM"`, its line id as the `code`, any HCPCS
  Level II modifiers it needs (for example `RT`/`LT`, `GA`/`GZ`, `PT`), and its units.
- If a HCPCS Level II code must be billed instead of a charge-master line (for example a
  G-code replacement), report the HCPCS code and leave that charge-master line out.
- Convert drug doses into HCPCS billing units using the code's descriptor.

## Output

Write one JSON object to `/app/output/coded_claim.json`:

```json
{
  "query_needed": false,
  "query_text": "",
  "codes": [
    {"code": "A41.51", "system": "ICD-10-CM", "role": "principal", "poa": "Y",
     "evidence": "exact words copied from the chart"},
    {"code": "0QS604Z", "system": "ICD-10-PCS", "role": "principal_procedure",
     "evidence": "exact words copied from the chart"},
    {"code": "J3301", "system": "HCPCS", "role": "line", "modifiers": ["JZ"], "units": 4,
     "evidence": "exact words copied from the chart"},
    {"code": "PROC1", "system": "CDM", "role": "line", "modifiers": ["RT"], "units": 1,
     "evidence": "exact words copied from the chart"}
  ]
}
```

Field rules:

- `system`: one of `ICD-10-CM`, `ICD-10-PCS`, `HCPCS`, `CDM`.
- `code`: a valid, billable FY2027 code. Write ICD-10-CM codes with the dot (`A41.51`).
  Charge-master lines use their line id.
- `role`:
  - diagnoses: `principal` (inpatient) or `first_listed` (outpatient/professional) for the main
    diagnosis, `secondary` for the rest
  - ICD-10-PCS procedures: `principal_procedure` or `procedure`
  - HCPCS and CDM claim lines: `line`
- `poa`: present-on-admission indicator (`Y`, `N`, `U`, `W`) for inpatient diagnoses only. Omit
  it for POA-exempt codes and for every non-inpatient encounter.
- `modifiers` and `units`: HCPCS and CDM lines only. Use one line per code + modifier combination.
- `evidence`: a short quote copied word for word from a chart file that supports the code.
  Do not paraphrase.

## Provider queries

If the documentation is not enough to assign a code correctly (for example a term with no
ICD-10-CM code such as "urosepsis", a missing stage, type or acuity, missing laterality, or a
diagnosis that conflicts with the clinical findings), do not guess:

- set `query_needed` to `true`
- write a compliant, non-leading provider query in `query_text`: cite the clinical indicators from
  the chart and give the provider answer options
- in `codes`, list only the codes that do not depend on the query's answer

Raise a query only when the documentation really requires one.

## Grading

A deterministic checker compares your claim with a hidden answer key.

- The answer gets 0 if it contains any invalid, non-billable, CPT or CDT code, or if a provider
  query was required and you did not raise one.
- Each expected code earns points for the code, and for its role, POA indicator, modifiers and
  units where they apply. You lose points when an evidence quote is not found in the chart.
- Codes that do not belong on the claim, known-wrong codes and unnecessary queries cost points.

List only the codes that belong on the claim, in reporting order.
