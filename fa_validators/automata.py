"""Small automata library: DFA, NFA, subset construction, product, minimisation, DOT export.

A missing transition always means "go to the trap state qD", which never accepts.
Machines read *symbols* (character classes such as U, L, D), not raw characters.
"""
import re
from collections import deque

TRAP = "qD"


def _nat(s):
    """Natural sort key so that d2 < d10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


class DFA:
    def __init__(self, alphabet, start, accepts, delta, name=""):
        self.alphabet = list(alphabet)
        self.start = start
        self.accepts = set(accepts)
        self.delta = dict(delta)  # (state, symbol) -> state
        self.name = name
        self.members = {}         # filled by minimise(): new state -> original states

    # ---- running -----------------------------------------------------
    def step(self, s, a):
        if s == TRAP:
            return TRAP
        return self.delta.get((s, a), TRAP)

    def run(self, symbols):
        s, trace = self.start, []
        for a in symbols:
            n = self.step(s, a)
            trace.append((s, a, n))
            s = n
        return s in self.accepts, trace

    def accepts_word(self, symbols):
        return self.run(symbols)[0]

    # ---- structure ---------------------------------------------------
    def reachable(self):
        """Reachable states in BFS order (may include TRAP)."""
        order, seen, q = [self.start], {self.start}, deque([self.start])
        while q:
            s = q.popleft()
            for a in self.alphabet:
                n = self.step(s, a)
                if n not in seen:
                    seen.add(n)
                    order.append(n)
                    q.append(n)
        return order

    def live_states(self):
        return [s for s in self.reachable() if s != TRAP]

    def size(self):
        """Number of live (non-trap) reachable states."""
        return len(self.live_states())

    # ---- minimisation (Moore partition refinement) ----------------------
    def minimise(self):
        states = set(self.reachable()) | {TRAP}
        block = {s: (s in self.accepts) for s in states}
        count = len(set(block.values()))
        while True:
            sig = {s: (block[s], tuple(block[self.step(s, a)] for a in self.alphabet)) for s in states}
            ids = {}
            new = {s: ids.setdefault(sig[s], len(ids)) for s in states}
            if len(ids) == count:
                break
            block, count = new, len(ids)
        trap_block = block[TRAP]
        # name the blocks m0, m1, ... in BFS order from the start state
        names, members = {}, {}

        def name_of(s):
            b = block[s]
            if b == trap_block:
                return TRAP
            if b not in names:
                names[b] = f"m{len(names)}"
            return names[b]

        delta, seen, q = {}, {name_of(self.start)}, deque([self.start])
        done = set()
        while q:
            s = q.popleft()
            if block[s] in done:
                continue
            done.add(block[s])
            ns = name_of(s)
            members.setdefault(ns, [])
            for a in self.alphabet:
                t = self.step(s, a)
                nt = name_of(t)
                if nt != TRAP:
                    delta[(ns, a)] = nt
                    if block[t] not in done:
                        q.append(t)
        for s in self.reachable():
            n = name_of(s)
            if n != TRAP and n in members:
                members[n].append(s)
        acc = {name_of(s) for s in self.accepts if name_of(s) != TRAP}
        m = DFA(self.alphabet, name_of(self.start), acc, delta, self.name + " (minimal)")
        m.members = {k: sorted(v, key=_nat) for k, v in members.items()}
        return m

    def complement(self):
        live = set(self.live_states())
        delta = dict(self.delta)
        # make the trap explicit so that it can accept
        for s in list(live):
            for a in self.alphabet:
                if (s, a) not in delta:
                    delta[(s, a)] = "dead"
        for a in self.alphabet:
            delta[("dead", a)] = "dead"
        return DFA(self.alphabet, self.start, (live | {"dead"}) - self.accepts, delta, "not " + self.name)


def product(dfas, name=""):
    """Intersection of several DFAs over the same alphabet (reachable part only)."""
    alpha = dfas[0].alphabet
    start = tuple(d.start for d in dfas)
    delta, seen, q = {}, {start}, deque([start])
    while q:
        s = q.popleft()
        for a in alpha:
            parts = tuple(d.step(x, a) for d, x in zip(dfas, s))
            if TRAP in parts:
                continue
            delta[(s, a)] = parts
            if parts not in seen:
                seen.add(parts)
                q.append(parts)
    acc = {s for s in seen if all(x in d.accepts for d, x in zip(dfas, s))}
    return DFA(alpha, start, acc, delta, name)


class NFA:
    """NFA without epsilon moves; delta maps (state, symbol) to a set of states."""

    def __init__(self, alphabet, start, accepts, delta, name=""):
        self.alphabet = list(alphabet)
        self.start = start
        self.accepts = set(accepts)
        self.delta = {k: set(v) for k, v in delta.items()}
        self.name = name

    def states(self):
        s = {self.start} | self.accepts
        for (q, _), ts in self.delta.items():
            s.add(q)
            s |= ts
        return s

    def accepts_word(self, symbols):
        cur = {self.start}
        for a in symbols:
            cur = set().union(*[self.delta.get((q, a), set()) for q in cur]) if cur else set()
        return bool(cur & self.accepts)

    def to_dfa(self):
        """Subset construction. Returns a DFA whose states are named like {d1,q1}."""
        def nm(fs):
            return "{" + ",".join(sorted(fs, key=_nat)) + "}"
        start = frozenset([self.start])
        delta, seen, q = {}, {start}, deque([start])
        while q:
            S = q.popleft()
            for a in self.alphabet:
                T = frozenset().union(*[self.delta.get((x, a), set()) for x in S])
                if not T:
                    continue
                delta[(nm(S), a)] = nm(T)
                if T not in seen:
                    seen.add(T)
                    q.append(T)
        acc = {nm(S) for S in seen if S & self.accepts}
        return DFA(self.alphabet, nm(start), acc, delta, self.name + " (subset DFA)")


# ---------------------------------------------------------------------------
# Graphviz export
# ---------------------------------------------------------------------------
def to_dot(m, groups=None, rankdir="LR", title=None, hide_trap=True, fontsize=13):
    """Return Graphviz DOT text. `groups` maps a label to a list of symbols that it replaces."""
    groups = groups or {}
    if isinstance(m, DFA):
        edges = {}
        for (s, a), t in m.delta.items():
            edges.setdefault((s, t), []).append(a)
        states = m.live_states()
    else:
        edges = {}
        for (s, a), ts in m.delta.items():
            for t in ts:
                edges.setdefault((s, t), []).append(a)
        states = sorted(m.states(), key=_nat)
    out = ["digraph G {", f"  rankdir={rankdir};", "  bgcolor=white; pad=0.2;",
           f'  node [shape=circle, fontname="Helvetica", fontsize={fontsize}, width=0.55, fixedsize=false];',
           f'  edge [fontname="Helvetica", fontsize={fontsize - 2}];']
    if title:
        out.append(f'  labelloc=t; label="{title}"; fontname="Helvetica-Bold"; fontsize=16;')
    out.append('  __start [shape=point, width=0.12];')
    for s in states:
        shape = "doublecircle" if s in m.accepts else "circle"
        out.append(f'  "{s}" [shape={shape}];')
    out.append(f'  __start -> "{m.start}";')
    for (s, t), syms in edges.items():
        labels, left = [], list(syms)
        for g, members in groups.items():
            if set(members) <= set(left):
                labels.append(g)
                left = [x for x in left if x not in members]
        labels += [x for x in m.alphabet if x in left]
        out.append(f'  "{s}" -> "{t}" [label="{", ".join(labels)}"];')
    out.append("}")
    return "\n".join(out)
