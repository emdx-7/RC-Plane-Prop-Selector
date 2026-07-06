# Propeller merge — notes (build this later)

Goal: combine APC (simulated) and UIUC (empirical) into one file per physical
prop in `propeller/`, with **separate fields** for simulated vs empirical data.

## TODO: document the simulated-vs-empirical data difference
(Deferred — user asked to note this and do it later.)
Quick version to expand later:
- **APC (simulated)**: dense grid over RPM x forward-speed. Dimensional
  (thrust_N, power_W, torque_Nm) PLUS coefficients (J, Ct, Cp, eff, mach).
  Smooth model output; wide RPM range (1000..~23000).
- **UIUC (empirical)**: wind-tunnel measurements. Non-dimensional only
  (J, CT, CP, eta) at a handful of tested RPMs, plus static (RPM,CT,CP).
  Sparse, real, has scatter; narrow RPM range (~1500..7000). Also has measured
  blade geometry (r/R, c/R, beta) in the JSON.
- Key point for overlay: to compare on the same plot they must meet in a common
  space. J vs CT/CP/eta is the natural shared space (both have it, both
  dimensionless). Dimensional overlay needs air density + diameter assumptions.

## Merge output shape (planned)
`propeller/<name>.json` (+ maybe .csv per source):
    { meta: {...}, sources: { simulated: {...APC...}, empirical: {...UIUC...} } }
empirical = null when no UIUC match; simulated = null if ever APC-only pool used.

## MATCHING (investigated + validated 2026-07-04)

Match key = (brand-type, diameter_in, pitch_in, blades), computed on both sides.

Brand-type map (UIUC prefix -> APC type_raw suffix) -- ONLY these three, because
only these have real size overlap with APC (verified against APC's parsed size
list). Carbon (apccf) and folding (apcff/apc29ff) were investigated and DROPPED:
their UIUC sizes have essentially no APC size twin, so mapping them would risk
mis-pairing. They stay UIUC-only (empirical present, simulated=null).

    apcsp -> ""   (sport, no suffix)
    apce  -> "E"  (electric)
    apcsf -> "SF" (slow fly)

Result: 74 confident matches + 2 recovered by the decimal fix below = 76.

### Decimal-drop fix (UIUC filenames drop the decimal point)
UIUC encodes 13x6.5 as "13x65", 14x8.5 as "14x85" (same as APC's part number
13065E). Only TWO confident-brand props are affected: apce_13x65, apce_14x85.
Fix rule (no blind guessing): if a UIUC APC-brand prop's literal size has no APC
match, try inserting a decimal before the last pitch digit and accept ONLY if
that yields a real APC size. 13x65->13x6.5 (APC 13x6.5E exists, confirmed online
apcprop.com part APC13065E), 14x85->14x8.5 (APC 14x8.5E exists). Both validated;
no false positives. Also correct the stored pitch in the UIUC outputs for these.
Non-APC brands (ancf, ef, pl, kpf, vp...) have their own decimal quirks but
don't match APC, so only their own stored pitch matters, not matching.

### apcff / apc29ff are FREE FLIGHT, not folding (verified online 2026-07)
"FF" = Free Flight, NOT Folding blade. UIUC Vol-1/Vol-2 listing pages put these
under an "APC Free Flight" / "29 Free Flight" category. So apc29ff_9x5 is NOT the
same product as APC's catalog "9x5F" (F = Folding) even though size+blades match
exactly -- that near-match is a coincidence and merging it would be a mis-pair.
APC's Free Flight line has no matchable name in the parsed performance catalog,
so all four (apcff_4.2x4, apcff_9x4, apc29ff_9x4, apc29ff_9x5) stay UIUC-only.
