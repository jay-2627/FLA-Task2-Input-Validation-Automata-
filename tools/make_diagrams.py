"""Build docs/diagrams/*.png|svg and the browser demo docs/index.html.

Needs Graphviz ('dot' on the PATH).  Run from the repository root:
    python tools/make_diagrams.py
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fa_validators.automata import to_dot                      # noqa: E402
from fa_validators.validators import (APPS, MOB_DIGITS, PW_ALPHA, PW_MAX, PW_MIN,   # noqa: E402
                                      TIME_DIGITS, coverage_dfa, length_dfa)

DIAG = ROOT / "docs" / "diagrams"
DIAG.mkdir(parents=True, exist_ok=True)


def render(name, dot_text):
    src = DIAG / f"{name}.dot"
    src.write_text(dot_text)
    subprocess.run(["dot", "-Tpng", "-Gdpi=130", str(src), "-o", str(DIAG / f"{name}.png")], check=True)
    subprocess.run(["dot", "-Tsvg", str(src), "-o", str(DIAG / f"{name}.svg")], check=True)
    src.unlink()
    print("built", name)


def build():
    mob = APPS["mobile"]
    mob_groups = {"digit": MOB_DIGITS, "6-9": ["9", "6-8"]}
    render("mobile_nfa", to_dot(mob.nfa, groups=mob_groups, title="Mobile number: hand-written NFA"))
    render("mobile_dfa", to_dot(mob.dfa, groups=mob_groups, title="Mobile number: minimal DFA (24 states)"))
    render("time_dfa", to_dot(APPS["time"].dfa,
                              groups={"digit": TIME_DIGITS, "0-5": ["0-1", "2", "3", "4-5"], "0-3": ["0-1", "2", "3"]},
                              title="Time HH:MM: DFA (7 states, trap omitted)"))
    render("password_coverage", to_dot(coverage_dfa(), rankdir="TB",
                                       title="Password: which classes have been seen (U, L, D, S)"))
    render("password_length", to_dot(length_dfa(PW_MIN, PW_MAX), groups={"any": PW_ALPHA},
                                     title=f"Password: length counter, accepts {PW_MIN}-{PW_MAX}"))


def dfa_json(d):
    table = {}
    for (s, a), t in d.delta.items():
        table.setdefault(str(s), {})[a] = str(t)
    return {"start": str(d.start), "accepts": [str(x) for x in d.accepts], "delta": table}


def build_demo():
    data = {}
    for k, v in APPS.items():
        item = {"title": v.title, "language": v.language, "alphabet": v.alphabet_note,
                "accepted": v.accepted, "rejected": v.rejected, "limits": v.limits,
                "diagram": {"password": "password_coverage", "mobile": "mobile_dfa", "time": "time_dfa"}[k]}
        if k != "password":
            item["dfa"] = dfa_json(v.dfa)
        data[k] = item
    svgs = {}
    for p in DIAG.glob("*.svg"):
        text = p.read_text()
        svgs[p.stem] = text[text.index("<svg"):]
    html = (ROOT / "tools" / "demo_template.html").read_text()
    html = html.replace("__DATA__", json.dumps(data)).replace("__SVGS__", json.dumps(svgs))
    (ROOT / "docs" / "index.html").write_text(html)
    print("built docs/index.html")


if __name__ == "__main__":
    build()
    build_demo()
