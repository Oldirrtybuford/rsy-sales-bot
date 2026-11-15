"""Merge this run's state into the latest state.json from the repo.
Usage: python merge_state.py MINE.json REPO_state.json  (writes into REPO_state.json)
Keeps every seen sale from both, the newest blockTime, and retry counters
only for sales neither side has marked seen."""
import json, sys

SEEN_CAP = 300


def load(p):
    try:
        with open(p) as f:
            st = json.load(f)
    except Exception:
        st = {}
    st.setdefault("last_blockTime", 0)
    st.setdefault("seen", [])
    st.setdefault("attempts", {})
    return st


mine, theirs = load(sys.argv[1]), load(sys.argv[2])
seen = list(theirs["seen"])
have = set(seen)
for s in mine["seen"]:
    if s not in have:
        seen.append(s)
        have.add(s)
attempts = {}
for src in (theirs["attempts"], mine["attempts"]):
    for k, v in src.items():
        if k not in have:
            attempts[k] = max(attempts.get(k, 0), v) if isinstance(v, int) else v
out = {
    "last_blockTime": max(mine["last_blockTime"], theirs["last_blockTime"]),
    "seen": seen[-SEEN_CAP:],
    "attempts": attempts,
}
with open(sys.argv[2], "w") as f:
    json.dump(out, f, indent=1)
    f.write("\n")
