"""
Step 2 - Convert every subject's selected DICOM series to BIDS using dcm2bids.

Reads manifest.csv (from 01_build_manifest.py) and runs dcm2bids for each
subject, producing:
    ~/ppmi_bids/sub-<ID>/ses-M00/anat/sub-<ID>_ses-M00_T1w.nii.gz

RESUME SUPPORT (important for large re-runs):
Subjects that already have a T1w.nii.gz are SKIPPED automatically, so if
this crashes or you stop it partway through a big batch, re-running it just
picks up where it left off instead of redoing everyone from scratch.

TWO-PASS + CATCH-ALL STRATEGY
==============================
dcm2bids uses shell-style fnmatch globs (*, ?), not regex, and requires
each series to match exactly one rule ("Several Pairing" error otherwise).
  Pass 1: *T1*
  Pass 2: *MPRAGE*, *FSPGR*  (only for subjects pass 1 missed)
  Pass 3: *MP-RAGE*, *3D*    (loose catch-all, only for subjects still missing --
          check these manually afterwards, loose globs can mis-pair)

Run:
    python3 02_convert_to_bids.py
"""

import csv
import os
import shutil
import subprocess
import json

BASE_DIR     = "/Users/sarthakahuja/Desktop/ppmi_dataaaaaa"
MANIFEST_CSV = os.path.join(BASE_DIR, "manifest.csv")
BIDS_CONFIG  = os.path.expanduser("~/ppmi_bids_config.json")
BIDS_OUT     = os.path.expanduser("~/ppmi_bids")
SESSION      = "M00"

PASS_CONFIGS = [
    [("anat", "T1w", "*T1*")],
    [("anat", "T1w", "*MPRAGE*"), ("anat", "T1w", "*FSPGR*")],
    [("anat", "T1w", "*MP-RAGE*"), ("anat", "T1w", "*3D*")],
]


def write_bids_config(rules):
    config = {
        "descriptions": [
            {"datatype": dt, "suffix": sfx, "criteria": {"SeriesDescription": glob}}
            for dt, sfx, glob in rules
        ]
    }
    with open(BIDS_CONFIG, "w") as f:
        json.dump(config, f, indent=2)


def expected_t1w_path(subject):
    return os.path.join(
        BIDS_OUT, f"sub-{subject}", f"ses-{SESSION}", "anat",
        f"sub-{subject}_ses-{SESSION}_T1w.nii.gz"
    )


def run_dcm2bids(subject, dicom_dir):
    tmp_dir = os.path.join(BIDS_OUT, "tmp_dcm2bids", f"sub-{subject}_ses-{SESSION}")
    if os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir)
    sub_out_dir = os.path.join(BIDS_OUT, f"sub-{subject}")
    if os.path.isdir(sub_out_dir):
        shutil.rmtree(sub_out_dir)

    cmd = [
        "dcm2bids",
        "-d", dicom_dir,
        "-p", subject,
        "-s", SESSION,
        "-c", BIDS_CONFIG,
        "-o", BIDS_OUT,
        "--force_dcm2bids",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def main():
    with open(MANIFEST_CSV) as f:
        manifest = list(csv.DictReader(f))

    os.makedirs(BIDS_OUT, exist_ok=True)

    subjects = []
    already_done = 0
    for row in manifest:
        if row["dicom_dir"] == "NOT_FOUND" or not os.path.isdir(row["dicom_dir"]):
            print(f"⏭️  Skipping sub-{row['subject']} (DICOM folder not found)")
            continue
        if os.path.isfile(expected_t1w_path(row["subject"])):
            already_done += 1
            continue
        subjects.append(row)

    print(f"{already_done} subject(s) already converted (skipped).")
    print(f"{len(subjects)} subject(s) to convert now.\n")

    remaining = {row["subject"]: row for row in subjects}
    success = []

    for pass_num, rules in enumerate(PASS_CONFIGS, start=1):
        if not remaining:
            break

        write_bids_config(rules)
        glob_desc = " | ".join(g for _, _, g in rules)
        print(f"\n{'#'*60}")
        print(f"# PASS {pass_num}: matching SeriesDescription against {glob_desc}")
        print(f"# {len(remaining)} subject(s) remaining")
        print(f"{'#'*60}")

        still_remaining = {}

        for subject, row in remaining.items():
            print(f"\nConverting sub-{subject}  ({row['group']}, visit={row['visit']})")
            result = run_dcm2bids(subject, row["dicom_dir"])

            expected = expected_t1w_path(subject)
            if os.path.isfile(expected):
                print(f"  ✅ -> {expected}")
                success.append(subject)
            else:
                if result.returncode != 0:
                    print("  STDERR:", result.stderr[-300:])
                still_remaining[subject] = row

        remaining = still_remaining

    failed = list(remaining.keys())

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(success)} converted now, {already_done} already done, "
          f"{len(failed)} failed")
    print(f"{'='*60}")
    if failed:
        print("Failed subjects (inspect SeriesDescription manually):", failed)
    print(f"\nBIDS output: {BIDS_OUT}")


if __name__ == "__main__":
    main()
