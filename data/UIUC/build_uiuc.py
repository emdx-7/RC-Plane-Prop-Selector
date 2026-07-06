"""
Batch-process the UIUC propeller database into a CSV + JSON pair per prop.

Reads the .txt files under inputs/volume-*/ (extracted from UIUC-propDB.zip) and
groups them by propeller. A UIUC prop is identified by its filename:

    <mfr>_<DIAxPITCH>[_<Nb>]_<specimen>_<rpm>.txt   performance sweep at one RPM
    <mfr>_<DIAxPITCH>[_<Nb>]_static_<specimen>.txt   static (zero-airspeed) sweep
    <mfr>_<DIAxPITCH>[_<Nb>]_geom.txt                blade planform (r/R, c/R, beta)

For each prop we write:

    outputs/<prop>.csv   all performance + static rows stacked, ONE ROW PER point:
                         kind, rpm, J, CT, CP, eta
                         (static rows use J=0, eta=0 -- true at zero airspeed;
                          'kind' is "dynamic" or "static")

    outputs/<prop>.json  scalar metadata + the blade geometry from the geom file:
                         name, mfr, diameter_in, pitch_in, blades, volume,
                         rpm range, and geometry = [{r_R, c_R, beta}, ...]
                         (planform stays null; geometry now holds the real data)

<prop> filename is "<mfr>_<size>[_<Nb>]"; if the same prop appears in two volumes
the volume is appended so nothing gets silently merged.

Run:  py build_uiuc.py   ->  writes outputs/*.csv and outputs/*.json
"""

import csv
import json
import os
import re
from collections import defaultdict

from parse_uiuc import parse_table


SIZE_RE = re.compile(r"^([\d.]+)x([\d.]+)$")   # "8.5x6" -> ("8.5","6")
RPM_RE = re.compile(r"^\d+$")                   # trailing rpm field is all digits
NB_RE = re.compile(r"^(\d+)b$")                 # blade-count token like "3b"


# --- decimal-drop fix (only for APC-brand UIUC props) ---------------------
# UIUC filenames drop the decimal point: apce_13x65 really means 13x6.5. This
# only matters for props that should match APC. We fix ONLY when inserting a
# decimal before the last pitch digit yields a REAL APC size (self-validating,
# so we can't invent a size that doesn't exist). APC sizes are read from the
# APC output .json filenames (which are "<size><suffix>").
APC_BRAND_PREFIXES = ("apce", "apcsf", "apcsp")   # brands that map to APC


def load_apc_sizes():
    """Return the set of real APC (diameter, pitch) sizes, from APC outputs.

    Each APC output file is named "<DIAxPITCH><suffix>.json". We strip the
    suffix and keep the numeric DIAxPITCH so we can check UIUC guesses."""
    here = os.path.dirname(os.path.abspath(__file__))
    apc_out = os.path.join(here, "..", "APC", "outputs")
    sizes = set()
    if not os.path.isdir(apc_out):
        return sizes                       # APC not built yet -> no fix, no harm
    size_re = re.compile(r"^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)")
    for fn in os.listdir(apc_out):
        if not fn.endswith(".json"):
            continue
        m = size_re.match(fn)
        if m:
            sizes.add((float(m.group(1)), float(m.group(2))))
    return sizes


def fix_decimal(mfr, diameter, pitch, pitch_str, apc_sizes):
    """If this APC-brand prop's size has no APC twin, try putting a decimal
    before the last pitch digit and accept ONLY if that hits a real APC size.
    Returns the corrected (pitch, pitch_str), else the originals unchanged."""
    if not mfr.startswith(APC_BRAND_PREFIXES):
        return pitch, pitch_str            # non-APC brand: leave its size alone
    if (diameter, pitch) in apc_sizes:
        return pitch, pitch_str            # already a real APC size: nothing to do
    if "." in pitch_str or len(pitch_str) < 2:
        return pitch, pitch_str            # already has a decimal / too short to split
    guess_str = pitch_str[:-1] + "." + pitch_str[-1]   # "65" -> "6.5"
    guess = float(guess_str)
    if (diameter, guess) in apc_sizes:     # validated: real APC size
        return guess, guess_str
    return pitch, pitch_str                # no valid APC match: leave as-is


# --- millimeter-size fix ---------------------------------------------------
# A few UIUC micro/indoor brands give sizes in MILLIMETERS, not inches (e.g.
# pl_100x80 is 100mm x 80mm ~= 3.9in x 3.1in, not a 100-inch prop). Real props
# top out around 21in in this database, then there is a clean gap up to 57mm+,
# so any diameter over this cutoff is treated as mm and converted to inches,
# rounded to the nearest 0.5in. The converted size string is prefixed with '~'
# to flag that it is an approximate inch conversion.
MM_CUTOFF_IN = 40.0        # a "diameter_in" above this is really millimeters


def mm_to_inch(diameter, pitch):
    """If diameter looks like mm (> cutoff), convert both dia and pitch to inches
    rounded to 0.5in and flag it. Returns (dia_in, pitch_in, is_mm)."""
    if diameter <= MM_CUTOFF_IN:
        return diameter, pitch, False
    d = round(diameter / 25.4 * 2) / 2     # mm -> in, nearest 0.5
    p = round(pitch / 25.4 * 2) / 2
    return d, p, True


def half_str(x):
    """Format a 0.5-rounded number compactly: 4.0 -> '4', 4.5 -> '4.5'."""
    return str(int(x)) if x == int(x) else str(x)


def classify(fn, apc_sizes=frozenset()):
    """Decode a UIUC filename into (mfr, size, blades, kind, rpm, specimen).

    kind is 'dynamic' | 'static' | 'geom'. Returns None if the name has no
    recognizable DIAxPITCH token (not a data file we understand)."""
    base = fn[:-4] if fn.lower().endswith(".txt") else fn
    parts = base.split("_")

    # locate the size token; everything before it is the manufacturer tag
    size_i = next((i for i, p in enumerate(parts) if SIZE_RE.match(p)), None)
    if size_i is None:
        return None
    mfr = "_".join(parts[:size_i])
    m = SIZE_RE.match(parts[size_i])
    diameter, pitch = float(m.group(1)), float(m.group(2))

    # UIUC drops decimals in filenames; restore for APC-brand props if it hits
    # a real APC size (13x65 -> 13x6.5). 'size' string is rebuilt to match.
    pitch, pitch_str = fix_decimal(mfr, diameter, pitch, m.group(2), apc_sizes)
    size_str = f"{m.group(1)}x{pitch_str}"

    # a handful of brands are in mm -> convert to approx inches, flag with '~'
    diameter, pitch, is_mm = mm_to_inch(diameter, pitch)
    if is_mm:
        size_str = f"~{half_str(diameter)}x{half_str(pitch)}"

    tail = parts[size_i + 1:]

    # optional blade-count token right after size (e.g. "3b")
    blades = 2
    if tail and NB_RE.match(tail[0]):
        blades = int(NB_RE.match(tail[0]).group(1))
        tail = tail[1:]

    if tail == ["geom"]:
        kind, rpm, specimen = "geom", None, None
    elif tail and tail[0] == "static":
        kind, rpm, specimen = "static", None, (tail[1] if len(tail) > 1 else "")
    elif tail and RPM_RE.match(tail[-1]):
        kind, rpm = "dynamic", int(tail[-1])
        specimen = tail[-2] if len(tail) > 1 else ""
    else:
        return None                      # unrecognized tail shape

    return {
        "mfr": mfr, "size": size_str, "diameter_in": diameter,
        "pitch_in": pitch, "blades": blades, "kind": kind,
        "rpm": rpm, "specimen": specimen,
    }


# CSV columns for the stacked performance + static rows
CSV_HEADER = ["kind", "rpm", "J", "CT", "CP", "eta"]


def collect(in_root):
    """Walk inputs/volume-*/ and bucket every file by prop key.

    Returns dict: key -> {'info':..., 'volume':..., 'files':[(kind, path, rpm)]}
    where key = (mfr, size, blades).
    """
    apc_sizes = load_apc_sizes()
    props = defaultdict(lambda: {"info": None, "volumes": set(), "files": []})
    for vol in sorted(os.listdir(in_root)):
        vdir = os.path.join(in_root, vol)
        if not os.path.isdir(vdir):
            continue
        for fn in sorted(os.listdir(vdir)):
            if not fn.lower().endswith(".txt"):
                continue
            info = classify(fn, apc_sizes)
            if info is None:
                continue
            key = (info["mfr"], info["size"], info["blades"])
            props[key]["info"] = info
            props[key]["volumes"].add(vol)
            props[key]["files"].append((info["kind"], os.path.join(vdir, fn),
                                        info["rpm"]))
    return props


def out_name(key, volumes):
    """Base filename for a prop; append volume if it spans more than one so the
    two cross-volume props don't collide."""
    mfr, size, blades = key
    name = f"{mfr}_{size}" + (f"_{blades}b" if blades != 2 else "")
    if len(volumes) > 1:
        name += "_" + "-".join(sorted(v.replace("volume-", "v") for v in volumes))
    return name


def build_rows(files):
    """Read every performance + static file for a prop into stacked CSV rows."""
    rows = []
    for kind, path, rpm in files:
        if kind == "geom":
            continue
        headers, table = parse_table(path)
        for r in table:
            if kind == "dynamic":
                # header: J CT CP eta   (rpm comes from the filename)
                J, CT, CP, eta = r[0], r[1], r[2], (r[3] if len(r) > 3 else 0.0)
                rows.append(["dynamic", rpm, J, CT, CP, eta])
            else:  # static -> header: RPM CT CP  (J and eta are 0 at zero speed)
                srpm, CT, CP = int(r[0]), r[1], r[2]
                rows.append(["static", srpm, 0.0, CT, CP, 0.0])
    # sort by kind then rpm then J so the file reads in a sensible order
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    return rows


def build_geometry(files):
    """Read the geom file (if any) into a list of {r_R, c_R, beta} dicts."""
    for kind, path, _ in files:
        if kind == "geom":
            headers, table = parse_table(path)
            return [{"r_R": r[0], "c_R": r[1], "beta": r[2]} for r in table]
    return None


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    in_root = os.path.join(here, "inputs")
    out_dir = os.path.join(here, "outputs")
    os.makedirs(out_dir, exist_ok=True)

    props = collect(in_root)
    written = 0
    for key, bucket in props.items():
        info = bucket["info"]
        volumes = bucket["volumes"]
        name = out_name(key, volumes)

        rows = build_rows(bucket["files"])
        geometry = build_geometry(bucket["files"])

        # CSV of stacked performance + static points
        with open(os.path.join(out_dir, f"{name}.csv"), "w", newline="",
                  encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            for r in rows:
                w.writerow([r[0], r[1]] + [round(float(x), 4) for x in r[2:]])

        rpms = [r[1] for r in rows]
        meta = {
            "name": name,
            "mfr": info["mfr"],
            "size": info["size"],
            "diameter_in": info["diameter_in"],
            "pitch_in": info["pitch_in"],
            "blades": info["blades"],
            "volumes": sorted(volumes),
            "rpm_min": min(rpms) if rpms else None,
            "rpm_max": max(rpms) if rpms else None,
            "n_points": len(rows),
            "geometry": geometry,   # blade planform from the geom file, or null
            "planform": None,       # reserved (APC-side placeholder mirror)
        }
        with open(os.path.join(out_dir, f"{name}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        written += 1

    print(f"wrote {written} UIUC props to {out_dir}")


if __name__ == "__main__":
    main()
