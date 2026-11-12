"""Case variants: synthetic charts + gold answers.

Each playbook example (ICD-01 … ICD-10) is a TEMPLATE. Each "edge case that changes the
answer" in the playbook becomes a VARIANT: same story, one detail flipped, different gold.

Gold status: the base variants copy the playbook's output tables. Variants marked
review="derived" apply the playbook's own edge-case rule but the exact code list was written
here. ALL gold must be signed off by a credentialed coder (CCS/CPC) before training use.

Code-set note: the reference bundle is FY2027, so every encounter is dated inside FY2027
(discharge / date of service 2026-10-01 .. 2027-09-30). All patients are fictional.

License rule: no CPT (AMA) or CDT (ADA) content anywhere — not in charts, gold, or answers.
Services whose procedure code would be CPT appear as hospital charge-master lines ("CDM",
e.g. PROC1) with a plain-language description written here; the agent reports only the
public parts of those lines (HCPCS Level II modifiers, units, or a HCPCS Level II replacement).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class G:  # one gold code / claim line
    code: str
    system: str                      # ICD-10-CM | ICD-10-PCS | HCPCS | CDM (charge-master line, no CPT)
    evidence: str                    # a quote that exists in the chart (used by the oracle)
    role: str | None = None          # principal | first_listed | secondary | principal_procedure | procedure | line
    poa: str | None = None           # Y | N | U | W | None (not scored)
    modifiers: list[str] | None = None
    units: int | None = None
    accept: list[str] = field(default_factory=list)   # equally correct alternative codes


@dataclass
class Case:
    id: str
    template: str
    title: str
    setting: str                     # inpatient | office | ed | observation | outpatient_lab | asc
    claim: str                       # facility_inpatient | professional | outpatient_facility
    dates: dict
    docs: dict[str, str]
    codes: list[G]
    query_needed: bool = False
    query_topic: str = ""
    optional: list[str] = field(default_factory=list)    # neither rewarded nor penalised
    forbidden: list[str] = field(default_factory=list)   # extra heavy penalty if billed
    tags: list[str] = field(default_factory=list)
    review: str = "playbook"         # playbook | derived
    cdm_lines: list[str] = field(default_factory=list)  # charge-master line ids present in the chart


INPT = dict(admit="2026-10-12", discharge="2026-10-17")
OFFICE = dict(service="2026-10-20")

# ── ICD-01 Sepsis ─────────────────────────────────────────────────────────
SEPSIS_HP = """HISTORY AND PHYSICAL — admitted from ED 10/12/2026
68-year-old woman with 2 days of dysuria, rigors and confusion.
Vitals on arrival: T 39.2 C, BP 78/40, HR 122. BP 78/40 despite 30 mL/kg fluids; norepinephrine started.
Labs: lactate 4.6 mmol/L. Creatinine 2.4 (baseline 0.8). UA: positive nitrites, >50 WBC.
Assessment: septic shock, suspected urinary source. Admit to ICU.
"""

CASES: list[Case] = [
    Case("ICD01-A", "ICD-01", "Sepsis with septic shock due to E. coli UTI, all POA", "inpatient",
         "facility_inpatient", INPT,
         {"hp.txt": SEPSIS_HP,
          "labs.txt": "Urine culture 10/13/2026: Escherichia coli > 100,000 CFU/mL.\nBlood cultures: no growth.\n",
          "progress_day2.txt": "Day 2: AKI is sepsis-associated, creatinine improving. Weaning norepinephrine.\n",
          "discharge_summary.txt": "DISCHARGE SUMMARY 10/17/2026\nFinal diagnosis: Septic shock due to E. coli urinary tract infection with sepsis-associated acute kidney injury.\nAll conditions present on admission.\n"},
         [G("A41.51", "ICD-10-CM", "Septic shock due to E. coli urinary tract infection", "principal", "Y"),
          G("R65.21", "ICD-10-CM", "Septic shock", "secondary", "Y"),
          G("N39.0", "ICD-10-CM", "urinary tract infection", "secondary", "Y"),
          G("N17.9", "ICD-10-CM", "sepsis-associated acute kidney injury", "secondary", "Y")],
         optional=["B96.20"], tags=["sepsis_poa", "organism_in_combination_code"]),

    Case("ICD01-B", "ICD-01", "Sepsis developed after admission for E. coli UTI", "inpatient",
         "facility_inpatient", INPT,
         {"hp.txt": "HISTORY AND PHYSICAL — admitted 10/12/2026\n68-year-old woman with dysuria and frequency. T 38.1 C, BP 128/76, HR 96, lactate 1.4. Creatinine 0.9.\nAssessment: acute cystitis / urinary tract infection. Start IV ceftriaxone.\n",
          "labs.txt": "Urine culture 10/13/2026: Escherichia coli > 100,000 CFU/mL.\n",
          "progress_day2.txt": "Day 2 (10/13/2026): new hypotension BP 76/38 after fluids, lactate 4.1, creatinine 2.2. Norepinephrine started. Patient has developed septic shock due to E. coli UTI with sepsis-associated acute kidney injury. Sepsis was not present on admission.\n",
          "discharge_summary.txt": "DISCHARGE SUMMARY 10/17/2026\nReason for admission: E. coli urinary tract infection.\nHospital course: developed septic shock with sepsis-associated acute kidney injury on hospital day 2 (not present on admission).\n"},
         [G("N39.0", "ICD-10-CM", "E. coli urinary tract infection", "principal", "Y"),
          G("A41.51", "ICD-10-CM", "developed septic shock due to E. coli UTI", "secondary", "N"),
          G("R65.21", "ICD-10-CM", "developed septic shock", "secondary", "N"),
          G("N17.9", "ICD-10-CM", "sepsis-associated acute kidney injury", "secondary", "N")],
         optional=["B96.20"], tags=["sepsis_not_poa"]),

    Case("ICD01-C", "ICD-01", "'Urosepsis' documented — must query", "inpatient", "facility_inpatient", INPT,
         {"hp.txt": "HISTORY AND PHYSICAL — admitted 10/12/2026\n68-year-old woman with dysuria and fever. T 38.6 C, BP 118/70, HR 104.\nAssessment: urosepsis. Start IV ceftriaxone.\n",
          "discharge_summary.txt": "DISCHARGE SUMMARY 10/17/2026\nFinal diagnosis: urosepsis, improved on antibiotics.\n"},
         [], query_needed=True, query_topic="urosepsis has no code: clarify sepsis vs UTI",
         forbidden=["A41.9", "A41.51", "N39.0", "R65.20", "R65.21", "A41.89"], tags=["urosepsis_query"],
         review="derived"),

    Case("ICD01-D", "ICD-01", "Septic shock from UTI, organism not identified", "inpatient",
         "facility_inpatient", INPT,
         {"hp.txt": SEPSIS_HP,
          "labs.txt": "Urine culture 10/13/2026: no growth (antibiotics given before collection). Blood cultures: no growth.\n",
          "discharge_summary.txt": "DISCHARGE SUMMARY 10/17/2026\nFinal diagnosis: Septic shock due to urinary tract infection, organism not identified, with sepsis-associated acute kidney injury. All present on admission.\n"},
         [G("A41.9", "ICD-10-CM", "Septic shock due to urinary tract infection, organism not identified", "principal", "Y"),
          G("R65.21", "ICD-10-CM", "Septic shock", "secondary", "Y"),
          G("N39.0", "ICD-10-CM", "urinary tract infection", "secondary", "Y"),
          G("N17.9", "ICD-10-CM", "sepsis-associated acute kidney injury", "secondary", "Y")],
         forbidden=["A41.51", "B96.20"], tags=["sepsis_organism_unknown"], review="derived"),
]

# ── ICD-02 Diabetes + CKD + HTN (office) ─────────────────────────────────
def dm_note(ckd_line: str, extra: str = "", meds: str = "insulin glargine and metformin") -> str:
    return (f"OFFICE VISIT 10/20/2026 — diabetes follow-up\n72-year-old man.\n"
            f"Assessment and plan:\n1. T2DM, A1c 7.6, on {meds}. Continue current regimen.\n"
            f"2. {ckd_line}\n3. Hypertension controlled on lisinopril.\n{extra}")

DM_MEDS = "Medication list: insulin glargine 20 units nightly; metformin 1000 mg twice daily; lisinopril 20 mg daily.\n"

CASES += [
    Case("ICD02-A", "ICD-02", "T2DM with CKD 3b and hypertension", "office", "professional", OFFICE,
         {"office_note.txt": dm_note("CKD stage 3b, eGFR 38. No other cause of CKD documented."), "meds.txt": DM_MEDS},
         [G("E11.22", "ICD-10-CM", "T2DM, A1c 7.6", "first_listed"),
          G("I12.9", "ICD-10-CM", "Hypertension controlled on lisinopril", "secondary"),
          G("N18.32", "ICD-10-CM", "CKD stage 3b", "secondary"),
          G("Z79.4", "ICD-10-CM", "insulin glargine", "secondary"),
          G("Z79.84", "ICD-10-CM", "metformin", "secondary")],
         forbidden=["E11.65", "I10"], tags=["with_convention", "hcc"]),

    Case("ICD02-B", "ICD-02", "CKD stage not documented (labs only)", "office", "professional", OFFICE,
         {"office_note.txt": dm_note("Chronic kidney disease, follow renal function. eGFR 38 today."), "meds.txt": DM_MEDS},
         [G("E11.22", "ICD-10-CM", "T2DM, A1c 7.6", "first_listed"),
          G("I12.9", "ICD-10-CM", "Hypertension controlled on lisinopril", "secondary"),
          G("N18.9", "ICD-10-CM", "Chronic kidney disease", "secondary"),
          G("Z79.4", "ICD-10-CM", "insulin glargine", "secondary"),
          G("Z79.84", "ICD-10-CM", "metformin", "secondary")],
         query_needed=True, query_topic="CKD stage not documented; eGFR suggests stage 3b",
         forbidden=["N18.32", "N18.31", "N18.30"], tags=["ckd_stage_query"], review="derived"),

    Case("ICD02-C", "ICD-02", "Diabetes with ESRD on dialysis", "office", "professional", OFFICE,
         {"office_note.txt": dm_note("ESRD on hemodialysis three times weekly (Mon/Wed/Fri)."), "meds.txt": DM_MEDS},
         [G("E11.22", "ICD-10-CM", "T2DM, A1c 7.6", "first_listed"),
          G("I12.0", "ICD-10-CM", "Hypertension controlled on lisinopril", "secondary"),
          G("N18.6", "ICD-10-CM", "ESRD on hemodialysis", "secondary"),
          G("Z99.2", "ICD-10-CM", "on hemodialysis", "secondary"),
          G("Z79.4", "ICD-10-CM", "insulin glargine", "secondary"),
          G("Z79.84", "ICD-10-CM", "metformin", "secondary")],
         forbidden=["I12.9", "N18.32", "N18.5"], tags=["esrd_dialysis"], review="derived"),

    Case("ICD02-D", "ICD-02", "Provider breaks the diabetes-CKD link (ADPKD)", "office", "professional", OFFICE,
         {"office_note.txt": dm_note("CKD stage 3b, eGFR 38, due to autosomal dominant polycystic kidney disease, not related to diabetes. Diabetes has no complications."),
          "meds.txt": DM_MEDS},
         [G("E11.9", "ICD-10-CM", "Diabetes has no complications", "first_listed"),
          G("Q61.2", "ICD-10-CM", "autosomal dominant polycystic kidney disease", "secondary"),
          G("I12.9", "ICD-10-CM", "Hypertension controlled on lisinopril", "secondary"),
          G("N18.32", "ICD-10-CM", "CKD stage 3b", "secondary"),
          G("Z79.4", "ICD-10-CM", "insulin glargine", "secondary"),
          G("Z79.84", "ICD-10-CM", "metformin", "secondary")],
         forbidden=["E11.22"], tags=["provider_breaks_link"], review="derived"),
]

# ── ICD-03 Heart failure + HTN + CKD 4 (inpatient) ───────────────────────
def hf_dc(hf: str) -> str:
    return (f"DISCHARGE SUMMARY 10/17/2026\n78-year-old woman admitted with dyspnea and edema.\n"
            f"Principal diagnosis: {hf}.\nOther diagnoses: Hypertension. CKD stage 4.\n"
            f"Treated with IV furosemide. All conditions present on admission.\n")

ECHO = "ECHOCARDIOGRAM 10/13/2026: LVEF 25%. Moderate global hypokinesis.\n"

CASES += [
    Case("ICD03-A", "ICD-03", "Acute on chronic systolic HF with HTN and CKD 4", "inpatient", "facility_inpatient", INPT,
         {"discharge_summary.txt": hf_dc("Acute on chronic systolic (HFrEF) heart failure, EF 25%"), "echo.txt": ECHO},
         [G("I13.0", "ICD-10-CM", "Hypertension. CKD stage 4", "principal", "Y"),
          G("I50.23", "ICD-10-CM", "Acute on chronic systolic (HFrEF) heart failure", "secondary", "Y"),
          G("N18.4", "ICD-10-CM", "CKD stage 4", "secondary", "Y")],
         forbidden=["I11.0", "I12.9", "I10"], tags=["htn_hf_ckd_triad"]),

    Case("ICD03-B", "ICD-03", "HF type not documented (only 'CHF'); EF on echo", "inpatient", "facility_inpatient", INPT,
         {"discharge_summary.txt": hf_dc("CHF exacerbation"), "echo.txt": ECHO},
         [G("I13.0", "ICD-10-CM", "Hypertension. CKD stage 4", "principal", "Y"),
          G("I50.9", "ICD-10-CM", "CHF exacerbation", "secondary", "Y"),
          G("N18.4", "ICD-10-CM", "CKD stage 4", "secondary", "Y")],
         query_needed=True, query_topic="heart failure type and acuity not documented (EF 25% on echo)",
         forbidden=["I50.23", "I50.22", "I50.21", "I50.20"], tags=["hf_type_query", "no_inference_from_ef"],
         review="derived"),

    Case("ICD03-C", "ICD-03", "Acute on chronic diastolic HF (HFpEF)", "inpatient", "facility_inpatient", INPT,
         {"discharge_summary.txt": hf_dc("Acute on chronic diastolic (HFpEF) heart failure, EF 60%"),
          "echo.txt": "ECHOCARDIOGRAM 10/13/2026: LVEF 60%. Grade II diastolic dysfunction.\n"},
         [G("I13.0", "ICD-10-CM", "Hypertension. CKD stage 4", "principal", "Y"),
          G("I50.33", "ICD-10-CM", "Acute on chronic diastolic (HFpEF) heart failure", "secondary", "Y"),
          G("N18.4", "ICD-10-CM", "CKD stage 4", "secondary", "Y")],
         forbidden=["I50.23"], tags=["hfpef"], review="derived"),
]

# ── ICD-04 Hip fracture (inpatient) ──────────────────────────────────────
def hip_ed(place: str) -> str:
    return (f"ED NOTE 10/12/2026\n84-year-old woman {place} and fell. No head strike.\n"
            f"X-ray: displaced intertrochanteric fracture, right femur. Closed injury, skin intact.\n")

HIP_DC = "DISCHARGE SUMMARY 10/17/2026\nPrincipal diagnosis: displaced intertrochanteric fracture of right femur after a fall (present on admission). Treated with cephalomedullary nail.\n"

def hip_op(approach_text: str) -> str:
    return ("OPERATIVE REPORT 10/13/2026\nProcedure: cephalomedullary nailing, right intertrochanteric femur fracture.\n"
            f"Closed reduction under fluoroscopy. {approach_text}\n"
            "Cephalomedullary nail inserted and locked. Fluoroscopy confirmed reduction.\n")

HIP_CM = [G("S72.141A", "ICD-10-CM", "displaced intertrochanteric fracture, right femur", "principal", "Y"),
          G("W18.09XA", "ICD-10-CM", "tripped over a rug", "secondary", accept=["W01.0XXA"]),
          G("Y92.013", "ICD-10-CM", "bedroom of her single-family house", "secondary")]

CASES += [
    Case("ICD04-A", "ICD-04", "Hip fracture, nail through stab incision (percutaneous)", "inpatient", "facility_inpatient", INPT,
         {"ed_note.txt": hip_ed("tripped over a rug in the bedroom of her single-family house"),
          "op_report.txt": hip_op("Guide wire and nail passed through a 2 cm stab incision over the greater trochanter; the fracture site was not exposed."),
          "discharge_summary.txt": HIP_DC},
         HIP_CM + [G("0QS636Z", "ICD-10-PCS", "the fracture site was not exposed", "principal_procedure")],
         optional=["Y99.8", "Y93.01", "Y93.89"], forbidden=["0QS606Z", "0QH636Z", "W22.8XXA"], tags=["pcs_approach_percutaneous", "7th_char"],
         review="derived"),

    Case("ICD04-B", "ICD-04", "Hip fracture, fracture site exposed (open)", "inpatient", "facility_inpatient", INPT,
         {"ed_note.txt": hip_ed("tripped over a rug in the bedroom of her single-family house"),
          "op_report.txt": hip_op("Reduction incomplete; a 10 cm lateral incision was made and the fracture site was exposed and reduced under direct vision before nail insertion."),
          "discharge_summary.txt": HIP_DC},
         HIP_CM + [G("0QS606Z", "ICD-10-PCS", "the fracture site was exposed", "principal_procedure")],
         optional=["Y99.8", "Y93.01", "Y93.89"], forbidden=["0QS636Z"], tags=["pcs_approach_open"], review="derived"),

    Case("ICD04-C", "ICD-04", "Hip fracture, approach wording ambiguous", "inpatient", "facility_inpatient", INPT,
         {"ed_note.txt": hip_ed("tripped over a rug in the bedroom of her single-family house"),
          "op_report.txt": hip_op("Nail inserted through a small incision over the greater trochanter."),
          "discharge_summary.txt": HIP_DC},
         HIP_CM, query_needed=True, query_topic="approach for nail insertion (open vs percutaneous) unclear",
         optional=["Y99.8", "Y93.01", "Y93.89"], forbidden=["0QS606Z", "0QS636Z"], tags=["pcs_approach_query"]),

    Case("ICD04-D", "ICD-04", "Hip fracture, fall in nursing home bedroom", "inpatient", "facility_inpatient", INPT,
         {"ed_note.txt": hip_ed("resident of a nursing home, tripped over a rug in her nursing home bedroom"),
          "op_report.txt": hip_op("Guide wire and nail passed through a 2 cm stab incision over the greater trochanter; the fracture site was not exposed."),
          "discharge_summary.txt": HIP_DC},
         [HIP_CM[0], HIP_CM[1], G("Y92.122", "ICD-10-CM", "nursing home bedroom", "secondary"),
          G("0QS636Z", "ICD-10-PCS", "the fracture site was not exposed", "principal_procedure")],
         optional=["Y99.8", "Y93.01", "Y93.89"], forbidden=["Y92.013", "0QS606Z"], tags=["place_of_occurrence"], review="derived"),
]

# ── ICD-05 Lap chole converted to open (inpatient) ───────────────────────
CHOLE_PATH = "PATHOLOGY: Gallbladder, cholecystectomy: acute calculous cholecystitis with cholelithiasis.\n"
CHOLE_DC = "DISCHARGE SUMMARY\n52-year-old man. Final diagnosis: acute calculous cholecystitis without obstruction.\n"

CASES += [
    Case("ICD05-A", "ICD-05", "Laparoscopic cholecystectomy converted to open", "inpatient", "facility_inpatient", INPT,
         {"op_report.txt": "OPERATIVE REPORT 10/13/2026\nLaparoscopic cholecystectomy started. Dense adhesions prevented safe dissection; procedure converted to open. Gallbladder removed completely through a right subcostal incision.\n",
          "pathology.txt": CHOLE_PATH, "discharge_summary.txt": CHOLE_DC},
         [G("K80.00", "ICD-10-CM", "acute calculous cholecystitis without obstruction", "principal", "Y"),
          G("Z53.31", "ICD-10-CM", "converted to open", "secondary"),
          G("0FT40ZZ", "ICD-10-PCS", "Gallbladder removed completely through a right subcostal incision", "principal_procedure"),
          G("0FJ44ZZ", "ICD-10-PCS", "Laparoscopic cholecystectomy started", "procedure")],
         forbidden=["0FT44ZZ"], tags=["converted_procedure"]),

    Case("ICD05-B", "ICD-05", "Laparoscopic cholecystectomy completed laparoscopically", "inpatient", "facility_inpatient", INPT,
         {"op_report.txt": "OPERATIVE REPORT 10/13/2026\nLaparoscopic cholecystectomy. Critical view of safety obtained. Gallbladder removed completely laparoscopically.\n",
          "pathology.txt": CHOLE_PATH, "discharge_summary.txt": CHOLE_DC},
         [G("K80.00", "ICD-10-CM", "acute calculous cholecystitis without obstruction", "principal", "Y"),
          G("0FT44ZZ", "ICD-10-PCS", "Gallbladder removed completely laparoscopically", "principal_procedure")],
         forbidden=["Z53.31", "0FT40ZZ", "0FJ44ZZ"], tags=["not_converted"], review="derived"),
]

# ── ICD-06 NSTEMI + PCI (inpatient) ──────────────────────────────────────
def cath(text: str) -> str:
    return f"CARDIAC CATH REPORT 10/13/2026\nAccess: right radial artery. Severe native coronary disease.\n{text}\nNo bifurcation lesions.\n"

MI_DC = "DISCHARGE SUMMARY\n61-year-old man. Principal diagnosis: NSTEMI (type 1), onset 10/12/2026. Coronary artery disease of native vessels, no angina history.\n"

CASES += [
    Case("ICD06-A", "ICD-06", "NSTEMI, one DES in each of two arteries", "inpatient", "facility_inpatient", INPT,
         {"cath_report.txt": cath("LAD: one drug-eluting stent placed. RCA: one drug-eluting stent placed."), "discharge_summary.txt": MI_DC},
         [G("I21.4", "ICD-10-CM", "NSTEMI (type 1)", "principal", "Y"),
          G("I25.10", "ICD-10-CM", "Coronary artery disease of native vessels", "secondary", "Y"),
          G("027134Z", "ICD-10-PCS", "LAD: one drug-eluting stent placed. RCA: one drug-eluting stent placed.", "principal_procedure")],
         optional=["B2111ZZ", "4A023N7"], forbidden=["027035Z", "02703DZ"], tags=["pcs_count_arteries"]),

    Case("ICD06-B", "ICD-06", "NSTEMI, two DES in one artery", "inpatient", "facility_inpatient", INPT,
         {"cath_report.txt": cath("LAD: two overlapping drug-eluting stents placed. RCA: no intervention."), "discharge_summary.txt": MI_DC},
         [G("I21.4", "ICD-10-CM", "NSTEMI (type 1)", "principal", "Y"),
          G("I25.10", "ICD-10-CM", "Coronary artery disease of native vessels", "secondary", "Y"),
          G("027035Z", "ICD-10-PCS", "LAD: two overlapping drug-eluting stents placed", "principal_procedure")],
         optional=["B2111ZZ", "4A023N7"], forbidden=["027134Z"], tags=["pcs_count_devices"], review="derived"),

    Case("ICD06-C", "ICD-06", "NSTEMI, balloon angioplasty only", "inpatient", "facility_inpatient", INPT,
         {"cath_report.txt": cath("LAD: balloon angioplasty only; no stent placed. RCA: no intervention."), "discharge_summary.txt": MI_DC},
         [G("I21.4", "ICD-10-CM", "NSTEMI (type 1)", "principal", "Y"),
          G("I25.10", "ICD-10-CM", "Coronary artery disease of native vessels", "secondary", "Y"),
          G("02703ZZ", "ICD-10-PCS", "balloon angioplasty only; no stent placed", "principal_procedure")],
         optional=["B2111ZZ", "4A023N7"], forbidden=["027034Z", "027134Z"], tags=["pcs_no_device"], review="derived"),
]

# ── ICD-07 Uncertain diagnosis by setting ────────────────────────────────
PNA_NOTE = "Cough and fever for 3 days. Probable pneumonia. Chest X-ray pending."

CASES += [
    Case("ICD07-A", "ICD-07", "ED visit: 'probable pneumonia'", "ed", "outpatient_facility", dict(service="2026-10-09"),
         {"ed_note.txt": f"ED NOTE 10/09/2026\n45-year-old man. {PNA_NOTE}\nDischarged home on oral antibiotics.\n"},
         [G("R05.1", "ICD-10-CM", "Cough and fever for 3 days", "first_listed"),
          G("R50.9", "ICD-10-CM", "Cough and fever for 3 days", "secondary")],
         forbidden=["J18.9"], tags=["uncertain_dx_outpatient"]),

    Case("ICD07-B", "ICD-07", "Inpatient discharge: 'probable pneumonia'", "inpatient", "facility_inpatient", INPT,
         {"discharge_summary.txt": f"DISCHARGE SUMMARY 10/17/2026\n45-year-old man admitted with: {PNA_NOTE}\nFinal diagnosis at discharge: probable pneumonia. Treated with IV ceftriaxone and azithromycin.\n"},
         [G("J18.9", "ICD-10-CM", "Final diagnosis at discharge: probable pneumonia", "principal", "Y")],
         forbidden=["R05.1", "R50.9"], tags=["uncertain_dx_inpatient"]),

    Case("ICD07-C", "ICD-07", "Observation stay: 'probable pneumonia'", "observation", "outpatient_facility", dict(service="2026-10-09"),
         {"observation_note.txt": f"OBSERVATION STAY 10/09/2026 - 10/10/2026 (outpatient observation status)\n45-year-old man. {PNA_NOTE}\nDischarged from observation: probable pneumonia.\n"},
         [G("R05.1", "ICD-10-CM", "Cough and fever for 3 days", "first_listed"),
          G("R50.9", "ICD-10-CM", "Cough and fever for 3 days", "secondary")],
         forbidden=["J18.9"], tags=["observation_uses_outpatient_rules"], review="derived"),
]

# ── ICD-08 Vitamin D LCD (outpatient lab, Medicare) ──────────────────────
# The lab test is charge-master line LAB1. The agent decides coverage from the LCD's ICD-10
# list and reports the HCPCS Level II liability modifier (GA / GZ / none).
def vitd(dx: str, abn: str) -> dict[str, str]:
    return {"lab_order.txt": f"LAB ORDER 10/22/2026 — Medicare Part B patient\nTest: 25-hydroxy vitamin D level\nDiagnosis on order: {dx}\nOrdering provider: Dr. A. Patel\n",
            "charge_lines.txt": "CHARGE LINES (procedure codes come from the hospital charge master)\nLAB1: 25-hydroxy vitamin D level, units 1\n",
            "coverage.txt": "Applicable Medicare policy for this lab's jurisdiction: LCD L33996 / Billing and Coding article A56798.\n",
            "abn.txt": abn,
            "specimen.txt": "Specimen drawn 10/22/2026 09:15.\n"}

CASES += [
    Case("ICD08-A", "ICD-08", "Vitamin D for fatigue, valid ABN", "outpatient_lab", "professional", dict(service="2026-10-22"),
         vitd("fatigue", "ABN (CMS-R-131) for the vitamin D test signed by patient 10/22/2026 08:55, before the specimen draw. Option 1 selected.\n"),
         [G("LAB1", "CDM", "LAB1: 25-hydroxy vitamin D level", "line", modifiers=["GA"], units=1),
          G("R53.83", "ICD-10-CM", "Diagnosis on order: fatigue", "first_listed")],
         tags=["lcd_not_covered_abn_valid"], cdm_lines=["LAB1"]),

    Case("ICD08-B", "ICD-08", "Vitamin D for fatigue, no ABN", "outpatient_lab", "professional", dict(service="2026-10-22"),
         vitd("fatigue", "No ABN on file for this order.\n"),
         [G("LAB1", "CDM", "LAB1: 25-hydroxy vitamin D level", "line", modifiers=["GZ"], units=1),
          G("R53.83", "ICD-10-CM", "Diagnosis on order: fatigue", "first_listed")],
         forbidden=["E55.9"], tags=["lcd_not_covered_no_abn"], review="derived", cdm_lines=["LAB1"]),

    Case("ICD08-C", "ICD-08", "Vitamin D for fatigue, ABN signed after the draw", "outpatient_lab", "professional", dict(service="2026-10-22"),
         vitd("fatigue", "ABN (CMS-R-131) for the vitamin D test signed by patient 10/22/2026 10:40.\n"),
         [G("LAB1", "CDM", "LAB1: 25-hydroxy vitamin D level", "line", modifiers=["GZ"], units=1),
          G("R53.83", "ICD-10-CM", "Diagnosis on order: fatigue", "first_listed")],
         tags=["abn_late"], review="derived", cdm_lines=["LAB1"]),

    Case("ICD08-D", "ICD-08", "Vitamin D with covered diagnosis documented", "outpatient_lab", "professional", dict(service="2026-10-22"),
         vitd("chronic kidney disease, stage 3b", "No ABN on file for this order.\n"),
         [G("LAB1", "CDM", "LAB1: 25-hydroxy vitamin D level", "line", modifiers=[], units=1),
          G("N18.32", "ICD-10-CM", "chronic kidney disease, stage 3b", "first_listed")],
         tags=["lcd_covered"], review="derived", cdm_lines=["LAB1"]),
]

# ── ICD-09 Screening colonoscopy (NCD 210.3) ─────────────────────────────
# The colonoscopy is charge-master line PROC1. Public decisions: PT modifier, whether the
# HCPCS Level II screening code (G0121 / G0105) replaces the line, and diagnosis order.
def colo(indication: str, finding: str, line: str,
         history: str = "Last colonoscopy 11 years ago (normal). No personal or family history of polyps or colorectal cancer.") -> dict[str, str]:
    return {"procedure_report.txt": f"COLONOSCOPY REPORT 10/27/2026 — Medicare patient, 66-year-old\nIndication: {indication}\nHistory: {history}\n"
                                    f"Findings: {finding}\nCecum reached; prep adequate.\n",
            "charge_lines.txt": f"CHARGE LINES (procedure codes come from the hospital charge master)\nPROC1: {line}, units 1\n"}

CASES += [
    Case("ICD09-A", "ICD-09", "Screening colonoscopy, polyp removed by snare, pathology pending", "asc", "professional", dict(service="2026-10-27"),
         {**colo("average-risk colorectal cancer screening", "6 mm polyp in the sigmoid colon, removed by hot snare.", "colonoscopy with snare removal of polyp"),
          "pathology.txt": "Pathology pending at time of coding.\n"},
         [G("PROC1", "CDM", "PROC1: colonoscopy with snare removal of polyp", "line", modifiers=["PT"], units=1),
          G("Z12.11", "ICD-10-CM", "average-risk colorectal cancer screening", "first_listed"),
          G("K63.5", "ICD-10-CM", "6 mm polyp in the sigmoid colon", "secondary")],
         forbidden=["G0121", "G0105", "D12.5"], tags=["screening_converted_pt"], cdm_lines=["PROC1"]),

    Case("ICD09-B", "ICD-09", "Screening colonoscopy, polyp removed, pathology adenoma", "asc", "professional", dict(service="2026-10-27"),
         {**colo("average-risk colorectal cancer screening", "6 mm polyp in the sigmoid colon, removed by hot snare.", "colonoscopy with snare removal of polyp"),
          "pathology.txt": "PATHOLOGY 10/29/2026: Sigmoid colon polyp, snare: tubular adenoma.\n"},
         [G("PROC1", "CDM", "PROC1: colonoscopy with snare removal of polyp", "line", modifiers=["PT"], units=1),
          G("Z12.11", "ICD-10-CM", "average-risk colorectal cancer screening", "first_listed"),
          G("D12.5", "ICD-10-CM", "Sigmoid colon polyp, snare: tubular adenoma", "secondary")],
         forbidden=["G0121", "G0105", "K63.5"], tags=["pathology_changes_dx"], cdm_lines=["PROC1"]),

    Case("ICD09-C", "ICD-09", "Screening colonoscopy, no findings", "asc", "professional", dict(service="2026-10-27"),
         colo("average-risk colorectal cancer screening", "Normal colon. No polyps.", "colonoscopy, diagnostic"),
         [G("G0121", "HCPCS", "average-risk colorectal cancer screening", "line", modifiers=[], units=1),
          G("Z12.11", "ICD-10-CM", "average-risk colorectal cancer screening", "first_listed")],
         forbidden=["PROC1", "G0105"], tags=["screening_normal_gcode"], review="derived", cdm_lines=["PROC1"]),

    Case("ICD09-D", "ICD-09", "Colonoscopy started for rectal bleeding (diagnostic)", "asc", "professional", dict(service="2026-10-27"),
         {**colo("rectal bleeding for 3 weeks", "6 mm polyp in the sigmoid colon, removed by hot snare. No other source of bleeding seen.",
                 "colonoscopy with snare removal of polyp"),
          "pathology.txt": "Pathology pending at time of coding.\n"},
         [G("PROC1", "CDM", "PROC1: colonoscopy with snare removal of polyp", "line", modifiers=[], units=1),
          G("K62.5", "ICD-10-CM", "rectal bleeding for 3 weeks"),
          G("K63.5", "ICD-10-CM", "6 mm polyp in the sigmoid colon")],
         forbidden=["Z12.11", "G0121", "G0105"], tags=["diagnostic_from_start"], review="derived", cdm_lines=["PROC1"]),
]

# ── ICD-10 Knee injection: drug units, wastage, laterality (office, Medicare) ─
# The injection is charge-master line INJ1. Public decisions: HCPCS J-code units (mg -> 10 mg
# billing units), JW/JZ wastage modifiers, RT/LT laterality, MUE check, diagnosis codes.
def knee(side: str, drug: str, vial: str, visit: str) -> dict[str, str]:
    return {"procedure_note.txt": f"PROCEDURE NOTE 11/03/2026 — Medicare patient\nDiagnosis: primary osteoarthritis, {side} knee.\n"
                                  f"{drug} injected into the {side} knee joint under ultrasound guidance; images saved with a written report.\n{vial}\n",
            "visit_note.txt": visit,
            "charge_lines.txt": f"CHARGE LINES (procedure codes come from the hospital charge master)\nINJ1: {side} knee joint injection with ultrasound guidance, units 1\n"}

VISIT_HTN = ("OFFICE VISIT 11/03/2026\nSeparately: blood pressure 168/96 today; uncontrolled hypertension. Increased amlodipine to 10 mg, "
             "ordered BMP, follow-up 2 weeks. (Separate problem from the knee.)\n")
VISIT_KNEE_ONLY = ("OFFICE VISIT 11/03/2026\nVisit for scheduled knee injection only. Decision to inject made at the prior visit. "
                   "No other problems addressed.\n")
SINGLE_40 = "Drug from a single-dose 40 mg vial; entire vial administered, nothing discarded."
TRIAM = "Triamcinolone acetonide 40 mg"

CASES += [
    Case("ICD10-A", "ICD-10", "Knee injection, single-dose vial fully used, separate HTN managed", "office", "professional", dict(service="2026-11-03"),
         knee("right", TRIAM, SINGLE_40, VISIT_HTN),
         [G("INJ1", "CDM", "INJ1: right knee joint injection", "line", modifiers=["RT"], units=1),
          G("J3301", "HCPCS", "Triamcinolone acetonide 40 mg", "line", modifiers=["JZ"], units=4),
          G("M17.11", "ICD-10-CM", "primary osteoarthritis, right knee"),
          G("I10", "ICD-10-CM", "uncontrolled hypertension")],
         forbidden=["M17.12", "M17.0"], tags=["drug_units", "jz", "laterality"], cdm_lines=["INJ1"]),

    Case("ICD10-B", "ICD-10", "Knee injection from a multi-dose vial", "office", "professional", dict(service="2026-11-03"),
         knee("right", TRIAM, "Drug drawn from a multi-dose 200 mg/5 mL vial.", VISIT_HTN),
         [G("INJ1", "CDM", "INJ1: right knee joint injection", "line", modifiers=["RT"], units=1),
          G("J3301", "HCPCS", "Triamcinolone acetonide 40 mg", "line", modifiers=[], units=4),
          G("M17.11", "ICD-10-CM", "primary osteoarthritis, right knee"),
          G("I10", "ICD-10-CM", "uncontrolled hypertension")],
         tags=["multi_dose_no_jw_jz"], review="derived", cdm_lines=["INJ1"]),

    Case("ICD10-C", "ICD-10", "Knee injection, single-dose 80 mg vial, 40 mg discarded", "office", "professional", dict(service="2026-11-03"),
         knee("right", TRIAM, "Drug drawn from a single-dose 80 mg vial; 40 mg administered and the remaining 40 mg discarded.", VISIT_HTN),
         [G("INJ1", "CDM", "INJ1: right knee joint injection", "line", modifiers=["RT"], units=1),
          G("J3301", "HCPCS", "40 mg administered", "line", modifiers=[], units=4),
          G("J3301", "HCPCS", "remaining 40 mg discarded", "line", modifiers=["JW"], units=4),
          G("M17.11", "ICD-10-CM", "primary osteoarthritis, right knee"),
          G("I10", "ICD-10-CM", "uncontrolled hypertension")],
         tags=["jw_wastage"], review="derived", cdm_lines=["INJ1"]),

    Case("ICD10-D", "ICD-10", "Knee injection only, no separate problem", "office", "professional", dict(service="2026-11-03"),
         knee("right", TRIAM, SINGLE_40, VISIT_KNEE_ONLY),
         [G("INJ1", "CDM", "INJ1: right knee joint injection", "line", modifiers=["RT"], units=1),
          G("J3301", "HCPCS", "Triamcinolone acetonide 40 mg", "line", modifiers=["JZ"], units=4),
          G("M17.11", "ICD-10-CM", "primary osteoarthritis, right knee")],
         forbidden=["I10"], tags=["no_separate_problem"], review="derived", cdm_lines=["INJ1"]),

    Case("ICD10-E", "ICD-10", "Left knee injection, 80 mg dose", "office", "professional", dict(service="2026-11-03"),
         knee("left", "Triamcinolone acetonide 80 mg", "Drug from two single-dose 40 mg vials; both fully administered, nothing discarded.", VISIT_KNEE_ONLY),
         [G("INJ1", "CDM", "INJ1: left knee joint injection", "line", modifiers=["LT"], units=1),
          G("J3301", "HCPCS", "Triamcinolone acetonide 80 mg", "line", modifiers=["JZ"], units=8),
          G("M17.12", "ICD-10-CM", "primary osteoarthritis, left knee")],
         forbidden=["M17.11", "I10"], tags=["laterality_left", "drug_units"], review="derived", cdm_lines=["INJ1"]),
]

def by_id() -> dict[str, Case]:
    return {c.id: c for c in CASES}
