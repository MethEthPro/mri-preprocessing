"""
Step 5 — Skull-strip every subject's registered T1w volume using FSL `bet`.

Finds all *_desc-Crop_res-1x1x1_T1w.nii.gz files under the CAPS directory and
runs bet on each, saving alongside as *_brain.nii.gz.

Run:
    python3 05_skull_strip.py
"""

import os
import glob
import subprocess

CAPS_DIR = os.path.expanduser("~/ppmi_caps")
BET_FRAC = "0.4"   # fractional intensity threshold; lower=keep more brain


def main():
    inputs = sorted(glob.glob(os.path.join(
        CAPS_DIR, "subjects", "sub-*", "ses-*", "t1_linear",
        "*_desc-Crop_res-1x1x1_T1w.nii.gz"
    )))

    if not inputs:
        print("❌ No registered T1w files found. Run 04_run_t1linear.py first.")
        return

    print(f"Found {len(inputs)} subjects to skull-strip.\n")

    success, failed = [], []

    for input_path in inputs:
        output_path = input_path.replace(
            "_desc-Crop_res-1x1x1_T1w.nii.gz", "_brain.nii.gz"
        )

        if os.path.isfile(output_path):
            print(f"⏭️  Already done: {os.path.basename(output_path)}")
            success.append(output_path)
            continue

        print(f"Running bet on {os.path.basename(input_path)} ...")
        cmd = ["bet", input_path, output_path, "-f", BET_FRAC, "-g", "0"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and os.path.isfile(output_path):
            print(f"  ✅ -> {os.path.basename(output_path)}")
            success.append(output_path)
        else:
            print(f"  ❌ FAILED: {result.stderr}")
            failed.append(input_path)

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(success)} succeeded, {len(failed)} failed")
    print(f"{'='*60}")
    if failed:
        for f in failed:
            print("  FAILED:", f)


if __name__ == "__main__":
    main()