"""
Step 1 - Build a manifest of (subject, image_id, group, dicom_folder) for the
FULL dataset.

Folder layout expected (as described):
    BASE_DIR/
        PD/
            <one or more .csv files, e.g. PD_1.csv, PD_2.csv>
            <subject folders, e.g. 3278/, 53060/, ...>
        SWEDD/
            <one .csv file>
            <subject folders>
        CONTROL/
            <one .csv file>
            <subject folders>

For each subject, picks the scan with Visit == "BL" (Baseline). If a subject
has no BL scan, falls back to the visit priority order below.

If a class has multiple CSVs (like PD_1.csv + PD_2.csv), all rows from all
CSVs in that folder are merged before picking the best row per subject. If
the SAME subject appears in more than one CSV (e.g. present in both PD
downloads), rows from all files are pooled and the usual visit-priority
logic picks the best one among all of them -- no duplicate subjects will
end up in the manifest.

Output: BASE_DIR/manifest.csv  (one row per subject)

Run:
    python3 01_build_manifest.py
"""

import csv
import os
import glob

# ---- EDIT THESE TWO IF YOUR PATHS DIFFER -----------------------------
BASE_DIR = "/Users/sarthakahuja/Desktop/ppmi_dataaaaaa"

# Folder name for each group on disk, and the group label used everywhere else
GROUPS = {
    "PD":      "PD",
    "SWEDD":   "SWEDD",
    "Control": "CONTROL",
}
# ------------------------------------------------------------------------

VISIT_PRIORITY = ["BL", "SC", "V01", "V02", "V03", "V04", "V05", "V06",
                   "V07", "V08", "V09", "V10", "V11", "V12"]


def load_all_rows_for_group(group_dir: str):
    """Read every *.csv directly inside group_dir and merge their rows."""
    csv_paths = sorted(glob.glob(os.path.join(group_dir, "*.csv")))
    if not csv_paths:
        print(f"  ⚠️  No CSV found in {group_dir}")
        return [], []

    all_rows = []
    for p in csv_paths:
        with open(p, newline="") as f:
            rows = list(csv.DictReader(f))
        print(f"  Loaded {len(rows):4d} rows from {os.path.basename(p)}")
        all_rows.extend(rows)
    return all_rows, csv_paths


def pick_best_row(rows):
    """From all rows for one subject (possibly pooled across CSVs), prefer BL."""
    for visit in VISIT_PRIORITY:
        for row in rows:
            if row["Visit"] == visit:
                return row
    return rows[0]


def find_dicom_folder(group_dir: str, subject: str, image_id: str) -> str:
    """
    Search under BASE_DIR/<group_dir>/<subject>/ for a folder named exactly
    <image_id> (e.g. "I1473172"), which contains the .dcm files.
    """
    pattern = os.path.join(group_dir, subject, "**", image_id)
    matches = glob.glob(pattern, recursive=True)
    matches = [m for m in matches if os.path.isdir(m)]
    return matches[0] if matches else None


def main():
    manifest = []
    dup_subject_count = 0

    for group, folder_name in GROUPS.items():
        group_dir = os.path.join(BASE_DIR, folder_name)
        print(f"\n[{group}] scanning {group_dir}")

        if not os.path.isdir(group_dir):
            print(f"  ⚠️  Folder does not exist, skipping: {group_dir}")
            continue

        rows, csv_paths = load_all_rows_for_group(group_dir)
        if not rows:
            continue

        rows_by_subject = {}
        for row in rows:
            subj = row["Subject"]
            rows_by_subject.setdefault(subj, []).append(row)

        n_dupes = sum(1 for r in rows_by_subject.values() if len(r) > 1)
        if n_dupes:
            print(f"  ℹ️  {n_dupes} subject(s) had rows in more than one CSV "
                  f"(or more than one scan) -- pooled and best row picked.")
            dup_subject_count += n_dupes

        for subject, subj_rows in rows_by_subject.items():
            best = pick_best_row(subj_rows)
            image_id = best["Image Data ID"]

            dicom_dir = find_dicom_folder(group_dir, subject, image_id)

            manifest.append({
                "group":       group,
                "subject":     subject,
                "image_id":    image_id,
                "visit":       best["Visit"],
                "description": best["Description"],
                "acq_date":    best["Acq Date"],
                "dicom_dir":   dicom_dir or "NOT_FOUND",
            })

    if not manifest:
        print("\n❌ No rows collected at all -- check BASE_DIR / folder names.")
        return

    found = sum(1 for m in manifest if m["dicom_dir"] != "NOT_FOUND")
    print(f"\nTotal subjects: {len(manifest)}  |  DICOM folders found: {found}")

    not_found = [m for m in manifest if m["dicom_dir"] == "NOT_FOUND"]
    if not_found:
        print(f"\n⚠️  Could not locate DICOM folder for {len(not_found)} subject(s):")
        for m in not_found[:30]:
            print(f"   {m['group']:8s} sub-{m['subject']:8s} "
                  f"image_id={m['image_id']:10s} visit={m['visit']}")
        if len(not_found) > 30:
            print(f"   ... and {len(not_found) - 30} more")

    out_path = os.path.join(BASE_DIR, "manifest.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=manifest[0].keys())
        writer.writeheader()
        writer.writerows(manifest)

    print(f"\n✅ Manifest written to: {out_path}")
    by_group = {}
    for m in manifest:
        by_group[m["group"]] = by_group.get(m["group"], 0) + 1
    for g, n in by_group.items():
        print(f"   {g:8s}: {n} subjects")


if __name__ == "__main__":
    main()
