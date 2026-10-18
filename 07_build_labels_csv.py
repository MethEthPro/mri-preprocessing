"""
Step 7 (FINAL) — Build the labels CSV for PPMIDataset, with REAL clinical
scores merged in from PPMI's clinical assessment downloads.

Clinical score sources (matched at Baseline visit, EVENT_ID == "BL";
falls back to "SC" for MoCA since some subjects only have a Screening MoCA):

    depression  <- MDS-UPDRS Part I, column NP1DPRS
                   ("Depressed mood" item, 0-4 scale)

    sleepiness  <- Epworth Sleepiness Scale, sum of ESS1..ESS8
                   (total score, 0-24 scale)

    cognition   <- Montreal Cognitive Assessment, column MCATOT
                   (total score, 0-30 scale)

Two output CSVs are created, ready for PPMIDataset:
  ~/ppmi_labels_pd_vs_nc.csv     (label: 1=PD, 0=NC)
  ~/ppmi_labels_nc_vs_swedd.csv  (label: 1=SWEDD, 0=NC)

Run:
    python3 07_build_labels_csv.py
"""

import csv
import os
import glob

BASE_DIR     = "/Users/sarthakahuja/Desktop/ppmi_dataaaaaa"
MANIFEST_CSV = os.path.join(BASE_DIR, "manifest.csv")
NIFTI_128_DIR = os.path.expanduser("~/ppmi_128")

# Clinical CSVs — adjust paths if you saved them elsewhere
ESS_CSV   = os.path.join(BASE_DIR, "Epworth_Sleepiness_Scale_12Jun2026.csv")
MOCA_CSV  = os.path.join(BASE_DIR, "Montreal_Cognitive_Assessment__MoCA__12Jun2026.csv")
UPDRS_CSV = os.path.join(BASE_DIR, "MDS-UPDRS_Part_I_12Jun2026.csv")

PREFERRED_EVENTS = ["BL", "SC"]   # try BL first, fall back to SC


def load_scores(csv_path, value_fn, preferred_events=PREFERRED_EVENTS):
    """
    Generic loader: returns {PATNO: score_value} using the first row per
    subject matching a preferred EVENT_ID (BL, then SC).

    value_fn(row) -> float  computes the score from a CSV row dict.
    """
    by_patno_event = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            patno = row["PATNO"]
            event = row["EVENT_ID"]
            by_patno_event.setdefault(patno, {})[event] = row

    scores = {}
    for patno, events in by_patno_event.items():
        for ev in preferred_events:
            if ev in events:
                try:
                    scores[patno] = value_fn(events[ev])
                except (ValueError, KeyError):
                    pass
                break
    return scores


def depression_value(row):
    return float(row["NP1DPRS"])


def sleepiness_value(row):
    total = 0
    for i in range(1, 9):
        total += int(row[f"ESS{i}"])
    return float(total)


def cognition_value(row):
    return float(row["MCATOT"])


def find_128_path(subject: str):
    pattern = os.path.join(NIFTI_128_DIR, f"sub-{subject}", "ses-*", "*_128.nii.gz")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def write_csv(rows, out_path, task_name):
    if not rows:
        print(f"⚠️  No rows for {task_name}, skipping.")
        return
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ {task_name}: wrote {len(rows)} rows to {out_path}")


def main():
    with open(MANIFEST_CSV) as f:
        manifest = list(csv.DictReader(f))

    print("Loading clinical scores...")
    depression_scores = load_scores(UPDRS_CSV, depression_value)
    sleepiness_scores = load_scores(ESS_CSV, sleepiness_value)
    cognition_scores  = load_scores(MOCA_CSV, cognition_value)
    print(f"  Depression scores loaded for {len(depression_scores)} subjects")
    print(f"  Sleepiness scores loaded for {len(sleepiness_scores)} subjects")
    print(f"  Cognition  scores loaded for {len(cognition_scores)} subjects\n")

    # Compute dataset means for imputing any missing values
    def mean_or_default(d, default=0.0):
        return sum(d.values()) / len(d) if d else default

    dep_mean   = mean_or_default(depression_scores)
    sleep_mean = mean_or_default(sleepiness_scores)
    cog_mean   = mean_or_default(cognition_scores)

    pd_vs_nc_rows = []
    nc_vs_swedd_rows = []
    missing_nifti = []
    missing_scores = []

    for row in manifest:
        subject = row["subject"]
        group   = row["group"]

        nifti_path = find_128_path(subject)
        if not nifti_path:
            missing_nifti.append((group, subject))
            continue

        dep   = depression_scores.get(subject)
        sleep = sleepiness_scores.get(subject)
        cog   = cognition_scores.get(subject)

        if dep is None or sleep is None or cog is None:
            missing_scores.append((group, subject,
                                    dep is None, sleep is None, cog is None))

        base_row = {
            "participant_id":   f"sub-{subject}",
            "session_id":       "ses-M00",
            "score_depression": dep   if dep   is not None else dep_mean,
            "score_sleepiness": sleep if sleep is not None else sleep_mean,
            "score_cognition":  cog   if cog   is not None else cog_mean,
            "nifti_path":       nifti_path,
        }

        if group == "PD":
            pd_vs_nc_rows.append({**base_row, "label": 1})
        elif group == "Control":
            pd_vs_nc_rows.append({**base_row, "label": 0})
            nc_vs_swedd_rows.append({**base_row, "label": 0})
        elif group == "SWEDD":
            nc_vs_swedd_rows.append({**base_row, "label": 1})

    if missing_nifti:
        print(f"⚠️  {len(missing_nifti)} subjects missing 128^3 NIfTI (skipped):")
        for g, s in missing_nifti:
            print(f"   {g:8s} sub-{s}")
        print()

    if missing_scores:
        print(f"⚠️  {len(missing_scores)} subjects missing one or more clinical "
              f"scores (filled with dataset mean):")
        for g, s, dep_m, sleep_m, cog_m in missing_scores:
            missing_list = []
            if dep_m: missing_list.append("depression")
            if sleep_m: missing_list.append("sleepiness")
            if cog_m: missing_list.append("cognition")
            print(f"   {g:8s} sub-{s}: missing {', '.join(missing_list)}")
        print()

    write_csv(pd_vs_nc_rows,
              os.path.expanduser("~/ppmi_labels_pd_vs_nc.csv"),
              "PD vs NC")
    write_csv(nc_vs_swedd_rows,
              os.path.expanduser("~/ppmi_labels_nc_vs_swedd.csv"),
              "NC vs SWEDD")

    pd_count    = sum(1 for r in pd_vs_nc_rows if r["label"] == 1)
    nc_count1   = sum(1 for r in pd_vs_nc_rows if r["label"] == 0)
    swedd_count = sum(1 for r in nc_vs_swedd_rows if r["label"] == 1)
    nc_count2   = sum(1 for r in nc_vs_swedd_rows if r["label"] == 0)

    print(f"\nPD vs NC:     {pd_count} PD, {nc_count1} NC")
    print(f"NC vs SWEDD:  {swedd_count} SWEDD, {nc_count2} NC")

    # Preview a few rows
    print("\nSample rows (PD vs NC):")
    for r in pd_vs_nc_rows[:3]:
        print(f"  {r['participant_id']}  label={r['label']}  "
              f"dep={r['score_depression']:.1f}  "
              f"sleep={r['score_sleepiness']:.1f}  "
              f"cog={r['score_cognition']:.1f}")


if __name__ == "__main__":
    main()