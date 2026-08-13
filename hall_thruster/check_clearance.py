"""Pairwise interference check on the assembly: any nonzero intersection volume
between two components that are NOT meant to touch is a modeling error."""
import itertools, build_thruster as B

# NOTHING is whitelisted any more. Three pairs that read zero here do so by design,
# and each is a real check rather than a mere absence:
#   * The keeper enclosure's cavity is FLUSH to the Ø18 cathode body, so those two
#     are tangent along four lines and share zero volume.
#   * The neutralizer is EXTERNAL - its housing was cut free of the thruster and
#     touches no part of it, so a reading against Magnetic_Core_Outer means the
#     assembly has been reattached.
#   * The feed line butts flush on the anode's upstream face rather than being
#     inserted.
OK = set()

parts = [(n, s) for s, n, _ in B.parts]
bad = 0
for (na, a), (nb, b) in itertools.combinations(parts, 2):
    hit = a & b
    v = 0.0 if hit is None else hit.volume
    if v < 1e-6:
        continue
    tag = "ok " if tuple(sorted((na, nb))) in {tuple(sorted(p)) for p in OK} else "BAD"
    if tag == "BAD":
        bad += 1
    print(f"  {tag} {na:22s} n {nb:22s} {v:10.1f} mm^3")
print("total volume", round(sum(s.volume for _, s in parts) / 1000, 1), "cm^3")
print("unintended interferences:", bad)
