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
