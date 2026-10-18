# PPMI Preprocessing v2 — full dataset run

## Expected folder layout (edit BASE_DIR in 01_build_manifest.py if different)
```
/Users/sarthakahuja/Desktop/ppmi_dataaaaaa/
    PD/
        PD_1.csv          <- your two PD downloads
        PD_2.csv
        3278/             <- subject folders (DICOMs inside)
        53060/
        ...
    SWEDD/
        SWEDD.csv          (or however it's named — script picks up any *.csv)
        <subject folders>
    CONTROL/
        CONTROL.csv
        <subject folders>
```
Each script auto-globs every `*.csv` directly inside a class folder, so PD's
two CSVs get merged automatically — no manual concatenation needed.

## Run order and where output lands

| Step | Script | Output location | What it contains |
|---|---|---|---|
| 1 | `01_build_manifest.py` | `BASE_DIR/manifest.csv` | One row per subject: group, subject ID, chosen image_id/visit, and the resolved DICOM folder path. This is the master list every later step reads from. |
| 2 | `02_convert_to_bids.py` | `~/ppmi_bids/sub-<ID>/ses-M00/anat/sub-<ID>_ses-M00_T1w.nii.gz` | Raw DICOM series converted to a single compressed NIfTI (.nii.gz) per subject, in standard BIDS layout. |
| 3 | `03_finalize_bids.py` | `~/ppmi_bids/participants.tsv`, `~/ppmi_bids/dataset_description.json` | Subject-to-diagnosis lookup table + BIDS dataset metadata (required for Clinica to accept the folder as valid BIDS). |
| 4 | `04_run_t1linear.py` | `~/ppmi_caps/subjects/sub-<ID>/ses-M00/t1_linear/*_desc-Crop_res-1x1x1_T1w.nii.gz` | Bias-field-corrected, affinely registered to MNI152 template, cropped to 169×208×179 @ 1mm. This is the "aligned" brain volume. |
| 5 | `05_skull_strip.py` | same folder, `*_brain.nii.gz` | Skull/scalp removed (FSL `bet`), so only brain tissue remains. |
| 6 | `06_resize_normalize.py` | `~/ppmi_128/sub-<ID>/ses-M00/sub-<ID>_ses-M00_128.nii.gz` | Resized to 128×128×128, intensities min-max normalized to [0,1]. This is the final tensor-ready volume used for model input. |
| 7 | `07_build_labels_csv.py` (optional) | `~/ppmi_labels_pd_vs_nc.csv`, `~/ppmi_labels_nc_vs_swedd.csv` | Final CSV pairing each subject's 128³ NIfTI path with its label + clinical scores (depression/sleepiness/cognition) — only needed if you also have the PPMI clinical assessment CSVs (UPDRS/ESS/MoCA); otherwise skip this step. |

Everything under `~/ppmi_bids`, `~/ppmi_caps`, `~/ppmi_128` is a fresh full
re-run — if you want to keep your old 60-subject pilot output, rename those
three folders first (or point `BIDS_OUT`/`CAPS_DIR`/`OUTPUT_DIR` in the
scripts somewhere else) before running this on the bigger dataset.

## Bottleneck / crash-prevention changes made for M4 16GB

1. **Resume support everywhere (steps 2 & 4).** Every script now checks if a
   subject's output already exists and skips it. If Clinica or dcm2bids
   crashes partway through hundreds of subjects, just re-run the same
   script — it won't redo finished work.
2. **`t1-linear` runs in small batches (default 10 subjects) with
   `--n_procs 3`** instead of one giant call across the whole dataset with
   auto-detected core count. ANTs registration is the single most
   memory-hungry step; letting Clinica launch as many parallel subjects as
   your M4 has cores can push past 16GB and get killed by macOS. If
   Activity Monitor still shows memory pressure (yellow/red) during a run,
   drop `N_PROCS` to 2 in `04_run_t1linear.py`.
3. **Clinica's temporary working directory is pinned and wiped between
   batches** (`BASE_DIR/clinica_work`). By default Clinica only deletes
   this on a clean finish — if anything crashes it silently fills your
   disk. Wiping it after every batch caps how much it can ever grow to.
4. Steps 1, 3, 5, 6, 7 are lightweight (single file I/O or single-threaded
   FSL/numpy calls) and run fine sequentially — no changes needed there
   beyond already-skip-if-done logic that was already in the originals.

## On your disk-space question

Rough space needed **beyond** your existing DICOMs, per subject, once all
steps finish:
- BIDS NIfTI (step 2): ~5–15 MB
- t1-linear CAPS output (step 4, incl. transform files): ~15–30 MB
- skull-stripped (step 5): ~5–10 MB (alongside the above)
- 128³ final volume (step 6): ~3–6 MB
- **~30–60 MB of new derived data per subject**, plus a transient spike of
  a few hundred MB per subject in `clinica_work` during step 4 (auto-deleted
  after each batch of 10).

So for e.g. 300 subjects total that's roughly 10–20 GB of new data, for
1000 subjects roughly 30–60 GB — well within your ~64GB of free space
(256GB total − 192GB used), **as long as your count is in that few-hundred
to ~1000 subject range**. If you're adding thousands of subjects, I'd
recommend checking free space directly rather than trusting an estimate:

```
df -h /Users/sarthakahuja
```

and telling me the actual subject count (or total DICOM folder size via
`du -sh /Users/sarthakahuja/Desktop/ppmi_dataaaaaa/{PD,SWEDD,CONTROL}`) so I
can give you a precise go/no-go instead of a range.


# PPMI MRI Preprocessing

## Linux Environment Setup

Clinica (the pipeline library used for bias correction, registration, and cropping) does not support Windows. It requires Linux or macOS, which is why the project uses Linux.

### 5a. IDE

Any IDE will work. VS Code with the Python and Remote-SSH extensions (if working on a remote machine) is the easiest default.

### 5b. System Packages

Before setting up Python, ensure the following packages are installed on Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y build-essential git curl wget unzip
```

### 5c. Install Miniconda

Clinica's installation documentation recommends using a Conda environment instead of a plain `venv`, since several dependencies, particularly ANTs, are easiest to install through `conda-forge`.

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# Restart the shell after installation
```

### 5d. Create the Environment

Use Python 3.11 to match the version already used for this project. Clinica supports Python versions 3.10–3.13, so Python 3.11 is within the supported range.

```bash
conda create -n clinica python=3.11 -y
conda activate clinica
```

---

## Step 6 — Install the Preprocessing Dependencies

With the `clinica` Conda environment active, install the required dependencies.

### Install ANTs

ANTs is used for bias correction and registration.

```bash
conda install -c conda-forge ants -y
```

### Install Clinica

```bash
pip install clinica
```

### Install dcm2bids

`dcm2bids` is used for DICOM-to-BIDS conversion.

```bash
pip install dcm2bids
```

### Install pydicom

`pydicom` is used by the diagnostic script to inspect DICOM headers.

```bash
pip install pydicom
```

### Install FSL

FSL is required for the skull-stripping step using `bet`. It is installed separately because it is not a pip or Conda package.

```bash
curl -O https://fsl.fmrib.ox.ac.uk/fsldownload/fslinstaller.py
python3 fslinstaller.py
```

Follow the installer prompts, then add FSL to your `PATH` as instructed by the installer.

### Verify the Installation

Run the following commands to verify that all dependencies are installed correctly:

```bash
clinica --version
antsRegistration --version
bet -h
dcm2bids --version
```

If any of these four commands fail, stop and resolve the issue before proceeding. Every subsequent step depends on these tools being available on `PATH`.

---

## Run the Preprocessing Pipeline

Run the following scripts in order from inside the `preprocessing_v2/` directory:

```bash
python3 01_build_manifest.py
# Builds manifest.csv from the group CSVs

python3 02_convert_to_bids.py
# Converts DICOM files to BIDS-compatible NIfTI files

python3 03_finalize_bids.py
# Finalizes BIDS metadata

python3 04_run_t1linear.py
# Performs bias correction, MNI registration, and cropping

python3 05_skull_strip.py
# Performs skull stripping using FSL BET

python3 06_resize_normalize.py
# Resizes images to 128^3 and applies min-max normalization
```

### Resuming Interrupted Runs

All scripts skip subjects that already have output. If a run is interrupted due to a crash, insufficient disk space, or the computer going to sleep, simply rerun the same script.

The pipeline will resume processing instead of restarting from scratch.
