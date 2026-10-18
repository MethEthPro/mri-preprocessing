"""
Step 6 — Resize every skull-stripped volume to 128x128x128 and apply
per-volume min-max normalisation to [0, 1], as specified in the paper.

Saves output to ~/ppmi_128/sub-<ID>/ses-M00/sub-<ID>_ses-M00_128.nii.gz
The affine is rescaled so the output displays correctly in viewers like
ITK-SNAP (fixes the "shifted/off-center" appearance).

Requires: pip install nibabel scipy

Run:
    python3 06_resize_normalize.py
"""

import os
import glob
import numpy as np
import nibabel as nib
from scipy.ndimage import zoom

CAPS_DIR   = os.path.expanduser("~/ppmi_caps")
OUTPUT_DIR = os.path.expanduser("~/ppmi_128")
TARGET_SHAPE = (128, 128, 128)


def resize_and_normalize(input_path: str, output_path: str):
    img  = nib.load(input_path)
    data = img.get_fdata(dtype=np.float32)

    factors = [t / s for t, s in zip(TARGET_SHAPE, data.shape)]
    resized = zoom(data, factors, order=3)

    resized = np.clip(resized, 0, None)
    vmin, vmax = resized.min(), resized.max()
    resized = (resized - vmin) / (vmax - vmin + 1e-8)

    # Rescale affine so the volume displays correctly (fixes shift in ITK-SNAP)
    new_affine = img.affine.copy()
    for i in range(3):
        new_affine[i, i] *= data.shape[i] / TARGET_SHAPE[i]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    nib.save(nib.Nifti1Image(resized, new_affine), output_path)
    return resized.shape, resized.min(), resized.max()


def main():
    inputs = sorted(glob.glob(os.path.join(
        CAPS_DIR, "subjects", "sub-*", "ses-*", "t1_linear", "*_brain.nii.gz"
    )))

    if not inputs:
        print("❌ No skull-stripped *_brain.nii.gz files found. Run 05_skull_strip.py first.")
        return

    print(f"Found {len(inputs)} subjects to resize.\n")

    for input_path in inputs:
        parts = input_path.split(os.sep)
        sub = next(p for p in parts if p.startswith("sub-"))
        ses = next(p for p in parts if p.startswith("ses-"))

        fname = os.path.basename(input_path).replace("_brain.nii.gz", "_128.nii.gz")
        output_path = os.path.join(OUTPUT_DIR, sub, ses, fname)

        if os.path.isfile(output_path):
            print(f"⏭️  Already done: {sub}/{ses}")
            continue

        shape, vmin, vmax = resize_and_normalize(input_path, output_path)
        print(f"✅ {sub}/{ses}  shape={shape}  range=[{vmin:.3f}, {vmax:.3f}]")

    print(f"\nDone. Output in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()