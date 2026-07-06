"""
Batch-process every APC .dat in inputs/ into a CSV + JSON pair per prop in outputs/.

For each prop we write two files:

    outputs/<name>.csv   the full sweep, ONE ROW PER (rpm, speed) point, with a
                         header row. Opens straight in Excel. Columns:
                         rpm, V_mph, J, Ct, Cp, eff, thrust_N, power_W,
                         torque_Nm, mach
                         (the grid shape is recovered later by grouping on rpm)

    outputs/<name>.json  the scalar metadata for that prop:
                         name, diameter_in, pitch_in, blades, type tags,
                         rpm/speed ranges, max thrust/power, and geometry/
                         planform placeholders (filled from PE0 files later)

Run:  py build_apc.py   ->  writes outputs/*.csv and outputs/*.json
"""

import csv
import json
import os
import re

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

# CSV columns in order: (header name, grid key in the parsed dict)
CSV_COLS = [
    ("rpm", "rpm"),
    ("V_mph", "V"),
    ("J", "J"),
    ("Ct", "Ct"),
    ("Cp", "Cp"),
    ("eff", "eff"),
    ("thrust_N", "thrust"),
    ("power_W", "power"),
    ("torque_Nm", "torque"),
    ("mach", "mach"),
]


def parse_name(name):
    """Pull diameter, pitch, blade count, and suffix tags out of a prop name.

    Examples:
        "10x10"        -> 10.0, 10.0, 2, "",   []
        "28x20-4"      -> 28.0, 20.0, 4, "",   []          (-4 = 4 blades)
        "8x4.1SF"      -> 8.0,  4.1,  2, "SF", ["Slow fly"]
        "20.5x10.5WPN" -> 20.5, 10.5, 2, "WPN", ["Wide chord", "Pattern"]
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


def write_csv(path, d):
    """Flatten the 2D grids to one row per (rpm, speed) point."""
    n_rpm, n_speed = d["rpm"].shape
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([h for h, _ in CSV_COLS])
        for i in range(n_rpm):
            for j in range(n_speed):
                w.writerow([round(float(d[key][i, j]), 4) for _, key in CSV_COLS])


def write_meta(path, d):
    """Scalar per-prop metadata (everything that is NOT a sweep field)."""
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
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    in_dir = os.path.join(here, "inputs")
    out_dir = os.path.join(here, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    dats = sorted(f for f in os.listdir(in_dir) if f.lower().endswith(".dat"))
    written = failed = 0
    for fn in dats:
        try:
            d = parse_file(os.path.join(in_dir, fn))
            write_csv(os.path.join(out_dir, f"{d['name']}.csv"), d)
            write_meta(os.path.join(out_dir, f"{d['name']}.json"), d)
            written += 1
        except Exception as e:
            print(f"  skip {fn}: {type(e).__name__} {e}")
            failed += 1

    print(f"wrote {written} props to {out_dir}  ({failed} skipped of {len(dats)})")


if __name__ == "__main__":
    main()
