"""
Step 3 — Create participants.tsv and dataset_description.json for the BIDS
folder, using the group labels (PD / SWEDD / Control) from manifest.csv.

Run:
    python3 03_finalize_bids.py
"""

import csv
import os
import json

BASE_DIR     = "/Users/sarthakahuja/Desktop/ppmi_dataaaaaa"
MANIFEST_CSV = os.path.join(BASE_DIR, "manifest.csv")
BIDS_OUT     = os.path.expanduser("~/ppmi_bids")


def main():
    with open(MANIFEST_CSV) as f:
        manifest = list(csv.DictReader(f))

    # dataset_description.json
    desc = {
        "Name": "PPMI",
        "BIDSVersion": "1.7.0",
        "DatasetType": "raw",
        "License": "PPMI Data Use Agreement",
        "Authors": ["Parkinson Progression Marker Initiative"],
        "Acknowledgements": (
            "Data used in preparation of this article were obtained from "
            "the Parkinson's Progression Markers Initiative (PPMI) database "
            "(www.ppmi-info.org/access-data-specimens/download-data)."
        ),
    }
    with open(os.path.join(BIDS_OUT, "dataset_description.json"), "w") as f:
        json.dump(desc, f, indent=2)

    # participants.tsv
    participants_path = os.path.join(BIDS_OUT, "participants.tsv")
    with open(participants_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["participant_id", "diagnosis_bl", "group"])
        for row in manifest:
            subj = row["subject"]
            group = row["group"]
            # Map to paper's labels: PD, NC (Healthy Control), SWEDD
            diag_map = {"PD": "PD", "Control": "HC", "SWEDD": "SWEDD"}
            writer.writerow([f"sub-{subj}", diag_map[group], group])

    print(f"Wrote {participants_path}")
    print(f"Wrote {os.path.join(BIDS_OUT, 'dataset_description.json')}")


if __name__ == "__main__":
    main()