"""
Merge APC (simulated) and UIUC (empirical) prop data into one file per prop.

Reads the already-built outputs:
    data/APC/outputs/<name>.csv + .json      (simulated: RPM x speed grid)
    data/UIUC/outputs/<name>.csv + .json      (empirical: wind-tunnel points)

and writes, into propeller/, ONE json per physical propeller:

    propeller/<name>.json
        { "meta":   {...combined identity + ranges...},
          "sources": { "simulated": {...APC...} | null,
                       "empirical": {...UIUC...} | null } }

Matching (see propeller/MERGE_NOTES.md for the full reasoning):
    key = (brand_type, diameter_in, pitch_in, blades), computed on both sides.
    Brand-type only maps for the three APC brands that have real size overlap:
        UIUC prefix  apcsp -> ""   apce -> "E"   apcsf -> "SF"
        APC suffix   type_raw is already exactly "", "E", or "SF"
    Every other prop (other APC suffixes, other UIUC mfrs) can't form a key on
    the opposite side, so it stays single-source (the missing side is null).
    Props with a null diameter (APC paren-variants like 13x6.5E(F2B)) can never
    match a number, so they safely stay APC-only.

The per-source "sweep" data (the CSV rows) is embedded straight into the JSON so
each propeller file is self-contained.

Run:  py build_propeller.py   ->  writes propeller/*.json
"""

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
APC_OUT = os.path.join(HERE, "data", "APC", "outputs")
UIUC_OUT = os.path.join(HERE, "data", "UIUC", "outputs")
PROP_DIR = os.path.join(HERE, "propeller")

# UIUC manufacturer prefix -> APC type_raw suffix. ONLY these three brands have
# validated size overlap with APC; everything else stays single-source.
UIUC_TO_APC_TYPE = {"apcsp": "", "apce": "E", "apcsf": "SF"}


def read_csv(path):
    """Read a sweep CSV into a list of dicts (numbers parsed as float)."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            row = {}
            for k, v in r.items():
                try:
                    row[k] = float(v)
                except ValueError:
                    row[k] = v          # e.g. the 'kind' text column in UIUC
            rows.append(row)
    return rows


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_side(out_dir):
    """Load every prop in an outputs dir as {name: {"meta":..., "rows":...}}."""
    props = {}
    for fn in os.listdir(out_dir):
        if not fn.endswith(".json"):
            continue
        name = fn[:-5]
        meta = read_json(os.path.join(out_dir, fn))
        rows = read_csv(os.path.join(out_dir, name + ".csv"))
        props[name] = {"meta": meta, "rows": rows}
    return props


def apc_key(meta):
    """(brand_type, diameter, pitch, blades) for an APC prop, or None if it
    can't form a key (null diameter, or a non-matching suffix)."""
    if meta["type_raw"] not in ("", "E", "SF"):
        return None
    if meta["diameter_in"] is None or meta["pitch_in"] is None:
        return None
    return (meta["type_raw"], meta["diameter_in"], meta["pitch_in"],
            meta["blades"])


def uiuc_key(meta):
    """(brand_type, diameter, pitch, blades) for a UIUC prop, or None if its
    manufacturer isn't one of the three mapped APC brands."""
    apc_type = UIUC_TO_APC_TYPE.get(meta["mfr"])
    if apc_type is None:
        return None
    return (apc_type, meta["diameter_in"], meta["pitch_in"], meta["blades"])


def merged_name(apc_meta, uiuc_meta):
    """Filename for the merged prop: prefer the APC name (the common part
    catalog name); fall back to the UIUC name for UIUC-only props."""
    return apc_meta["name"] if apc_meta else uiuc_meta["name"]


def build_meta(apc, uiuc):
    """Combined identity block. Numbers come from whichever side we have,
    preferring APC (it's the catalog reference)."""
    a = apc["meta"] if apc else None
    u = uiuc["meta"] if uiuc else None
    ref = a or u
    return {
        "name": merged_name(a, u),
        "diameter_in": (a or u)["diameter_in"],
        "pitch_in": (a or u)["pitch_in"],
        "blades": ref["blades"],
        "type": a["type"] if a else None,          # APC descriptive tags
        "apc_name": a["name"] if a else None,
        "uiuc_name": u["name"] if u else None,
        "has_simulated": a is not None,
        "has_empirical": u is not None,
    }


def build_simulated(apc):
    """APC side: the scalar meta plus the full RPM x speed sweep rows."""
    if apc is None:
        return None
    m = apc["meta"]
    return {
        "rpm_min": m["rpm_min"], "rpm_max": m["rpm_max"],
        "v_max_mph": m["v_max_mph"],
        "max_thrust_N": m["max_thrust_N"], "max_power_W": m["max_power_W"],
        "sweep": apc["rows"],
    }


def build_empirical(uiuc):
    """UIUC side: scalar meta, measured blade geometry, and the sweep points."""
    if uiuc is None:
        return None
    m = uiuc["meta"]
    return {
        "rpm_min": m["rpm_min"], "rpm_max": m["rpm_max"],
        "n_points": m["n_points"],
        "volumes": m["volumes"],
        "geometry": m["geometry"],
        "sweep": uiuc["rows"],
    }


def main():
    os.makedirs(PROP_DIR, exist_ok=True)

    apc_props = load_side(APC_OUT)
    uiuc_props = load_side(UIUC_OUT)

    # index each side by match key (only keyable props go in the index)
    apc_by_key = {}
    for name, p in apc_props.items():
        k = apc_key(p["meta"])
        if k is not None:
            apc_by_key[k] = name        # keys are unique per (type,dia,pitch,blades)
    uiuc_by_key = {}
    for name, p in uiuc_props.items():
        k = uiuc_key(p["meta"])
        if k is not None:
            uiuc_by_key[k] = name

    matched_keys = set(apc_by_key) & set(uiuc_by_key)

    used_apc, used_uiuc = set(), set()
    written = matched = apc_only = uiuc_only = 0

    def write_prop(apc, uiuc):
        meta = build_meta(apc, uiuc)
        doc = {
            "meta": meta,
            "sources": {
                "simulated": build_simulated(apc),
                "empirical": build_empirical(uiuc),
            },
        }
        with open(os.path.join(PROP_DIR, meta["name"] + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(doc, f, indent=2)

    # 1) matched props (both sides)
    for k in matched_keys:
        apc = apc_props[apc_by_key[k]]
        uiuc = uiuc_props[uiuc_by_key[k]]
        write_prop(apc, uiuc)
        used_apc.add(apc_by_key[k])
        used_uiuc.add(uiuc_by_key[k])
        written += 1
        matched += 1

    # 2) every remaining APC prop, simulated-only
    for name, p in apc_props.items():
        if name in used_apc:
            continue
        write_prop(p, None)
        written += 1
        apc_only += 1

    # 3) every remaining UIUC prop, empirical-only
    for name, p in uiuc_props.items():
        if name in used_uiuc:
            continue
        write_prop(None, p)
        written += 1
        uiuc_only += 1

    print(f"wrote {written} props to {PROP_DIR}")
    print(f"  matched (both sources): {matched}")
    print(f"  APC-only (simulated):   {apc_only}")
    print(f"  UIUC-only (empirical):  {uiuc_only}")


if __name__ == "__main__":
    main()
