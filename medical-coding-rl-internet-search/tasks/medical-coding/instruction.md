You are a certified medical coder. There are 36 encounters waiting to be coded in `/app/cases/`.
Code every one of them for billing.

Each case has its own folder, `/app/cases/<CASE_ID>/` (for example `/app/cases/ICD01-A/`):

- `chart/*.txt`: the provider documentation for that encounter
- `encounter.json`: care setting, claim type, dates, payer and code-set version

Code each case on its own, only from its own chart. The settings differ between cases: an
inpatient stay is billed on the facility claim (UB-04 / 837I) with a principal diagnosis and POA
indicators; office visits, outpatient lab services and colonoscopies are billed on the
professional claim (CMS-1500 / 837P); emergency department and observation visits are billed on
the hospital outpatient facility claim. Outpatient and professional claims use a first-listed
diagnosis and no POA.


## Output

Write one JSON file, `/app/output/coded_claims.json`. Its keys are the case ids (the folder
names in `/app/cases/`), and each value is that case's claim:

```json
{
  "ICD01-A": {
    "query_needed": false,
    "query_text": "",
    "codes": [
      {"code": "A41.51", "system": "ICD-10-CM", "role": "principal", "poa": "Y",
       "evidence": "exact words copied from this case's chart"},
      {"code": "0QS604Z", "system": "ICD-10-PCS", "role": "principal_procedure",
       "evidence": "exact words copied from this case's chart"}
    ]
  },
  "ICD10-A": {
    "query_needed": false,
    "query_text": "",
    "codes": [
      {"code": "J3301", "system": "HCPCS", "role": "line", "modifiers": ["JZ"], "units": 4,
       "evidence": "exact words copied from this case's chart"},
      {"code": "PROC1", "system": "CDM", "role": "line", "modifiers": ["RT"], "units": 1,
       "evidence": "exact words copied from this case's chart"}
    ]
  }
}
```

(The codes above only show the format; they are not the answers for those cases.)
Include every case. A case that is missing from the file scores 0.

Field rules for each claim:

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
- `evidence`: a short quote copied word for word from that case's chart that supports the code.
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
