"""Terminal demo.

  python -m fa_validators.cli                      accept/reject table for every application
  python -m fa_validators.cli mobile 919876543210  one string with the full transition trace
  python -m fa_validators.cli --stats              design comparison (state counts)
  python -m fa_validators.cli --limits             what each automaton cannot check
"""
import sys

from .validators import APPS, build_password

GREEN, RED, DIM, BOLD, END = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def verdict(ok):
    return f"{GREEN}ACCEPT{END}" if ok else f"{RED}REJECT{END}"


def show_tables():
    for v in APPS.values():
        print(f"\n{BOLD}{v.title}{END}  {DIM}{v.language}{END}")
        for label, words in (("accepted", v.accepted), ("rejected", v.rejected)):
            print(f"  -- {label} examples")
            for w in words:
                ok, _ = v.check(w)
                flag = "ok " if ok == (label == "accepted") else "BUG"
                print(f"     {w!r:22} {verdict(ok)}  {DIM}{flag}{END}")


def show_trace(key, text):
    v = APPS[key]
    ok, rows = v.check(text)
    print(f"{BOLD}{v.title}{END} (minimal DFA) on {text!r}")
    for i, s, ch, sym, t in rows:
        print(f"  {i:2}. d({s}, {ch!r} -> {sym}) = {t}")
    final = rows[-1][4] if rows else v.dfa.start
    print(f"  final state {final} -> {verdict(ok)}")


def show_stats():
    pw = APPS["password"].extra
    print(f"{BOLD}Design comparison (live states, trap state qD not counted){END}\n")
    print(f"  {'design':52}{'states':>7}")
    print(f"  {'Password 8-12: 6 small DFAs side by side':52}{pw['side_by_side']:>7}")
    print(f"  {'Password 8-12: product DFA (reachable part)':52}{pw['product'].size():>7}")
    print(f"  {'Password 8-12: product after minimisation':52}{pw['minimal'].size():>7}")
    wide = build_password(8, 16)
    print(f"  {'Password 8-16: product after minimisation':52}{wide['minimal'].size():>7}")
    m = APPS["mobile"]
    print(f"  {'Mobile number: hand-written NFA':52}{len(m.nfa.states()):>7}")
    print(f"  {'Mobile number: subset-construction DFA':52}{m.extra['subset'].size():>7}")
    print(f"  {'Mobile number: after minimisation':52}{m.extra['minimal'].size():>7}")
    print(f"  {'Time HH:MM: DFA (already minimal)':52}{APPS['time'].dfa.size():>7}")


def show_limits():
    for v in APPS.values():
        print(f"\n{BOLD}{v.title}{END}")
        for line in v.limits:
            print("  -", line)


def main(argv):
    if not argv:
        show_tables()
    elif argv[0] == "--stats":
        show_stats()
    elif argv[0] == "--limits":
        show_limits()
    elif argv[0] in APPS and len(argv) >= 2:
        show_trace(argv[0], argv[1])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
