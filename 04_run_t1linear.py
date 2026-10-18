"""
Step 4 - Run Clinica's t1-linear pipeline (bias correction + affine
registration to MNI + crop) for all subjects converted to BIDS.

BOTTLENECK OPTIMIZATIONS FOR M4 / 16GB RAM
===========================================
This is the heaviest step in the whole pipeline (ANTs registration per
subject). Two things cause crashes on a 16GB machine if left at defaults:

1. Clinica auto-detects your CPU core count and launches that many parallel
   subjects by default. Each running ANTs registration can use 1-2GB+ RAM,
   so on an M4 (8-10 cores) that can try to allocate 10-20GB at once and
   your Mac starts swapping / the process gets killed.
   -> We pin N_PROCS to a safe number (default 3). Raise it a bit if you
      watch Activity Monitor and see headroom; lower it to 2 if you still
      see memory pressure.

2. Clinica writes a large temporary "working directory" per subject while
   it runs (intermediate ANTs files), and only deletes it if the pipeline
   finishes cleanly. If it crashes, these pile up and silently eat disk.
   -> We point the working directory at BASE_DIR/clinica_work (easy to
      find and delete) and process subjects in small BATCHES, wiping the
      working directory between batches so it never grows unbounded.

Run:
    python3 04_run_t1linear.py
"""

import csv
import os
import shutil
import subprocess
import glob

BASE_DIR   = "/Users/sarthakahuja/Desktop/ppmi_dataaaaaa"
BIDS_DIR   = os.path.expanduser("~/ppmi_bids")
CAPS_DIR   = os.path.expanduser("~/ppmi_caps")
WORK_DIR   = os.path.join(BASE_DIR, "clinica_work")   # deleted between batches

N_PROCS    = 3     # parallel subjects; lower to 2 if Activity Monitor shows
                    # memory pressure / swap climbing during a run
BATCH_SIZE = 10     # subjects per clinica invocation


def already_done(sub, ses):
    pattern = os.path.join(
        CAPS_DIR, "subjects", sub, ses, "t1_linear",
        "*_desc-Crop_res-1x1x1_T1w.nii.gz"
    )
    return len(glob.glob(pattern)) > 0


def main():
    t1_files = glob.glob(os.path.join(BIDS_DIR, "sub-*", "ses-*", "anat", "*_T1w.nii.gz"))
    if not t1_files:
        print("❌ No T1w files found in BIDS directory. Run 02_convert_to_bids.py first.")
        return

    all_rows = []
    for f in t1_files:
        parts = f.split(os.sep)
        sub = next(p for p in parts if p.startswith("sub-"))
        ses = next(p for p in parts if p.startswith("ses-"))
        all_rows.append((sub, ses))

    os.makedirs(CAPS_DIR, exist_ok=True)

    rows = [(s, se) for s, se in all_rows if not already_done(s, se)]
    skipped = len(all_rows) - len(rows)
    print(f"{skipped} subject(s) already processed by t1-linear (skipped).")
    print(f"{len(rows)} subject(s) remaining, in batches of {BATCH_SIZE}, "
          f"n_procs={N_PROCS}.\n")

    if not rows:
        print("Nothing to do.")
        return

    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]

    for b_idx, batch in enumerate(batches, start=1):
        print(f"\n{'#'*60}")
        print(f"# BATCH {b_idx}/{len(batches)}  ({len(batch)} subjects)")
        print(f"{'#'*60}")

        tsv_path = os.path.join(BASE_DIR, "subjects_sessions_batch.tsv")
        with open(tsv_path, "w", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(["participant_id", "session_id"])
            for sub, ses in batch:
                writer.writerow([sub, ses])

        if os.path.isdir(WORK_DIR):
            shutil.rmtree(WORK_DIR)
        os.makedirs(WORK_DIR, exist_ok=True)

        cmd = [
            "clinica", "run", "t1-linear",
            BIDS_DIR, CAPS_DIR,
            "-tsv", tsv_path,
            "-wd", WORK_DIR,
            "--n_procs", str(N_PROCS),
        ]
        print("Command:", " ".join(cmd))
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"⚠️  Batch {b_idx} exited with code {result.returncode} "
                  f"(check output above). Continuing to next batch; "
                  f"re-run this script afterwards to retry failures.")

        # Reclaim disk: wipe the working directory now that the batch is done.
        if os.path.isdir(WORK_DIR):
            shutil.rmtree(WORK_DIR)

    outputs = glob.glob(os.path.join(
        CAPS_DIR, "subjects", "sub-*", "ses-*", "t1_linear",
        "*_desc-Crop_res-1x1x1_T1w.nii.gz"
    ))
    print(f"\n✅ Found {len(outputs)} registered T1w outputs in CAPS: {CAPS_DIR}")
    still_missing = len(all_rows) - len(outputs)
    if still_missing > 0:
        print(f"⚠️  {still_missing} subject(s) still missing output -- re-run this "
              f"script to retry (already-done subjects are skipped automatically).")


if __name__ == "__main__":
    main()
