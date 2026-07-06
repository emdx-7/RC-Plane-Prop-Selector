"""
Batch-parse all APC sport propeller files into a folder of processed JSON.

Reads every PER3_*.dat inside PERFILES_WEB-202602.zip (the 443 files in the
PERFILES2/ sport folder), runs the shared parse_apc.parse_file on each, and
writes one JSON per prop into demo/processed/.

Each JSON is:
    {
      "meta": {
        "name": "10x10", "diameter_in": 10.0, "pitch_in": 10.0, "blades": 2,
        "type": ["E", ...] (decoded suffix tags), "type_raw": "E",
        "rpm_min":..., "rpm_max":..., "v_max_mph":...,
        "max_thrust_N":..., "max_power_W":...,
        "geometry": null, "planform": null      # placeholders, filled from PE0 later
      },
      "grids": { "rpm":[[...]], "V":[[...]], "thrust":[[...]],
                 "power":[[...]], "eff":[[...]], "torque":[[...]], "mach":[[...]] }
    }

Grids are plain nested lists (JSON has no arrays of numbers), one value per
(rpm_index, speed_index) point -- same shape the plotter already expects.

Run:  py build_processed.py   ->  writes demo/processed/*.json
"""

import json
import os
import re
import tempfile
import zipfile

from parse_apc import parse_file


# APC name suffix tags -> meaning (from PROP-DATA-FILE nomenclature sheet).
# Only the letters that appear after the pitch in a part name.
SUFFIX_MEANING = {
    "E": "Electric",
    "F": "Folding blade",
    "MR": "Multi-rotor",
    "SF": "Slow fly",
    "R": "Reversible ESC",
    "W": "Wide chord",
    "N": "Narrow chord",
    "NN": "Very narrow chord",
    "PN": "Pattern",
    "P": "Pusher",
    "C": "Carbon",
    "T": "T-mount",
}

# grid quantities we carry through to JSON (must match parse_apc output keys)
GRID_KEYS = ["rpm", "V", "thrust", "power", "eff", "torque", "mach"]

ZIP_PATH = "PERFILES_WEB-202602.zip"      # relative to project root
SPORT_PREFIX = "PERFILES_WEB/PERFILES2/PER3_"   # sport folder inside the zip


def parse_name(name):
    """Pull diameter, pitch, blade count, and suffix tags out of a prop name.

    Examples:
        "10x10"      -> 10.0, 10.0, 2, "",   []
        "28x20-4"    -> 28.0, 20.0, 4, "",   []          (-4 = 4 blades)
        "8x4.1SF"    -> 8.0,  4.1,  2, "SF", ["Slow fly"]
        "20.5x10.5WPN" -> 20.5, 10.5, 2, "WPN", [...]
    """
    # diameter 'x' pitch, both allow decimals; optional '-N' blades; trailing letters
    m = re.match(r"^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(?:-(\d+))?([A-Za-z]*)$", name)
    if not m:
        return None, None, 2, "", []           # unparseable name: leave numbers blank
    diameter = float(m.group(1))
    pitch = float(m.group(2))
    blades = int(m.group(3)) if m.group(3) else 2
    suffix = m.group(4)

    # walk the suffix left-to-right, consuming each tag once. At each position
    # take the LONGEST matching key (so "SF" is read as Slow-fly, not S+F, and
    # "PN" as Pattern, not P+N). Unknown letters are skipped.
    keys_longest_first = sorted(SUFFIX_MEANING, key=len, reverse=True)
    tags = []
    s = suffix.upper()
    i = 0
    while i < len(s):
        for key in keys_longest_first:
            if s.startswith(key, i):
                tags.append(SUFFIX_MEANING[key])
                i += len(key)
                break
        else:
            i += 1                              # unknown letter, move on
    return diameter, pitch, blades, suffix, tags


def make_record(d):
    """Turn a parsed prop dict (numpy grids) into the JSON-ready record."""
    diameter, pitch, blades, suffix, tags = parse_name(d["name"])
    meta = {
        "name": d["name"],
        "diameter_in": diameter,
        "pitch_in": pitch,
        "blades": blades,
        "type_raw": suffix,
        "type": tags,
        "rpm_min": int(d["rpm"].min()),
        "rpm_max": int(d["rpm"].max()),
        "v_max_mph": round(float(d["V"].max()), 1),
        "max_thrust_N": round(float(d["thrust"].max()), 1),
        "max_power_W": round(float(d["power"].max()), 1),
        "geometry": None,      # placeholder: comes from PE0 files later
        "planform": None,      # placeholder: comes from PE0 files later
    }
    grids = {k: d[k].tolist() for k in GRID_KEYS}
    return {"meta": meta, "grids": grids}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)                 # project root holds the zip
    zip_path = os.path.join(root, ZIP_PATH)
    out_dir = os.path.join(here, "processed")
    os.makedirs(out_dir, exist_ok=True)

    z = zipfile.ZipFile(zip_path)
    entries = [n for n in z.namelist()
               if n.startswith(SPORT_PREFIX) and n.lower().endswith(".dat")]

    tmp = tempfile.mkdtemp()
    written = failed = 0
    for entry in sorted(entries):
        # parse_file reads from a path, so drop each file to a temp path first
        path = os.path.join(tmp, os.path.basename(entry))
        with open(path, "wb") as f:
            f.write(z.read(entry))
        try:
            d = parse_file(path)
            rec = make_record(d)
            out = os.path.join(out_dir, f"{d['name']}.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(rec, f)
            written += 1
        except Exception as e:
            print(f"  skip {os.path.basename(entry)}: {type(e).__name__} {e}")
            failed += 1

    print(f"wrote {written} props to {out_dir}  ({failed} skipped of {len(entries)})")


if __name__ == "__main__":
    main()
