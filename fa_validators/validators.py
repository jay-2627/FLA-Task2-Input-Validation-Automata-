"""The three validation applications: password policy, mobile number, 24-hour time.

Each application has
  * a classifier that maps a real character to a symbol of the automaton's alphabet,
  * the automaton itself (built here, never hand-typed as a giant table),
  * an independent regular-expression rule used only for cross-checking,
  * accepted / rejected example strings and a list of limitations.
"""
import re
from dataclasses import dataclass, field
from typing import Callable

from .automata import DFA, NFA, TRAP, product

# ===========================================================================
# 1. Password policy
# ===========================================================================
SPECIAL = "@#$%&*!"
PW_ALPHA = ["U", "L", "D", "S", "O"]
PW_MIN, PW_MAX = 8, 12


def classify_password(ch):
    if "A" <= ch <= "Z":
        return "U"
    if "a" <= ch <= "z":
        return "L"
    if "0" <= ch <= "9":
        return "D"
    if ch in SPECIAL:
        return "S"
    return "O"


def has_class(sym):
    """2-state DFA: has the class `sym` been seen yet?"""
    delta = {(0, a): 0 for a in PW_ALPHA}
    delta[(0, sym)] = 1
    delta.update({(1, a): 1 for a in PW_ALPHA})
    return DFA(PW_ALPHA, 0, [1], delta, f"has {sym}")


def length_dfa(lo, hi):
    """Counts characters; accepts when lo <= length <= hi; a (hi+1)-th character falls into the trap."""
    delta = {(n, a): n + 1 for n in range(hi) for a in PW_ALPHA}
    return DFA(PW_ALPHA, 0, range(lo, hi + 1), delta, f"length {lo}-{hi}")


def charset_dfa():
    """Rejects any character outside the four allowed classes (class O)."""
    delta = {(0, a): 0 for a in PW_ALPHA if a != "O"}
    return DFA(PW_ALPHA, 0, [0], delta, "allowed characters only")


def coverage_dfa():
    """16-state 'which classes have I seen?' machine; states are named like UL, DS, or '-' for none."""
    order = "ULDS"

    def nm(mask):
        return "".join(c for i, c in enumerate(order) if mask >> i & 1) or "-"
    delta = {}
    for mask in range(16):
        for a in PW_ALPHA:
            m2 = mask | (1 << order.index(a)) if a in order else mask
            delta[(nm(mask), a)] = nm(m2)
    return DFA(PW_ALPHA, "-", ["ULDS"], delta, "coverage")


def build_password(lo=PW_MIN, hi=PW_MAX):
    parts = [has_class(c) for c in "ULDS"] + [length_dfa(lo, hi), charset_dfa()]
    prod = product(parts, "password policy (product)")
    return {
        "components": parts,
        "side_by_side": sum(p.size() for p in parts),
        "product": prod,
        "minimal": prod.minimise(),
    }


def password_rule(w):
    return bool(PW_MIN <= len(w) <= PW_MAX and re.search("[A-Z]", w) and re.search("[a-z]", w)
                and re.search("[0-9]", w) and re.search("[@#$%&*!]", w)
                and re.fullmatch("[A-Za-z0-9@#$%&*!]+", w))


# ===========================================================================
# 2. Indian mobile number (NFA because of the optional 91 prefix)
# ===========================================================================
MOB_ALPHA = ["+", "0", "1", "9", "2-5", "6-8", "O"]
MOB_DIGITS = ["0", "1", "9", "2-5", "6-8"]
MOB_FIRST = ["9", "6-8"]  # digits 6-9


def classify_mobile(ch):
    if ch == "+":
        return "+"
    if ch in "019":
        return ch
    if ch in "2345":
        return "2-5"
    if ch in "678":
        return "6-8"
    return "O"


def build_mobile_nfa():
    d = {("s0", "+"): {"p1"}, ("p1", "9"): {"p2"}, ("p2", "1"): {"n"},
         ("s0", "9"): {"d1", "q1"}, ("q1", "1"): {"n"},       # '9' is both a prefix digit and a number digit
         ("s0", "0"): {"n"}, ("s0", "6-8"): {"d1"}}
    for a in MOB_FIRST:
        d[("n", a)] = {"d1"}
    for k in range(1, 10):
        for a in MOB_DIGITS:
            d[(f"d{k}", a)] = {f"d{k + 1}"}
    return NFA(MOB_ALPHA, "s0", ["d10"], d, "mobile number NFA")


def mobile_rule(w):
    return re.fullmatch(r"(\+91|91|0)?[6-9][0-9]{9}", w) is not None


# ===========================================================================
# 3. 24-hour time HH:MM
# ===========================================================================
TIME_ALPHA = ["0-1", "2", "3", "4-5", "6-9", ":", "O"]
TIME_DIGITS = ["0-1", "2", "3", "4-5", "6-9"]


def classify_time(ch):
    if ch in "01":
        return "0-1"
    if ch == "2":
        return "2"
    if ch == "3":
        return "3"
    if ch in "45":
        return "4-5"
    if ch in "6789":
        return "6-9"
    if ch == ":":
        return ":"
    return "O"


def build_time_dfa():
    d = {("t0", "0-1"): "t1", ("t0", "2"): "t2", ("t3", ":"): "t4"}
    for a in TIME_DIGITS:
        d[("t1", a)] = "t3"
        d[("t5", a)] = "t6"
    for a in ["0-1", "2", "3"]:
        d[("t2", a)] = "t3"
    for a in ["0-1", "2", "3", "4-5"]:
        d[("t4", a)] = "t5"
    return DFA(TIME_ALPHA, "t0", ["t6"], d, "time HH:MM")


def time_rule(w):
    return re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", w) is not None


# ===========================================================================
# Application records
# ===========================================================================
@dataclass
class Validator:
    key: str
    title: str
    alphabet_note: str
    language: str
    classify: Callable[[str], str]
    dfa: DFA
    rule: Callable[[str], bool]
    accepted: list
    rejected: list
    limits: list
    nfa: NFA = None
    extra: dict = field(default_factory=dict)

    def check(self, text):
        """Return (accepted?, rows) where each row is (i, state, char, symbol, next_state)."""
        syms = [self.classify(c) for c in text]
        ok, trace = self.dfa.run(syms)
        rows = [(i + 1, s, text[i], a, t) for i, (s, a, t) in enumerate(trace)]
        return ok, rows


def build_all():
    pw = build_password()
    mob_nfa = build_mobile_nfa()
    mob_sub = mob_nfa.to_dfa()
    mob_min = mob_sub.minimise()
    time_dfa = build_time_dfa()
    return {
        "password": Validator(
            "password", "Password policy",
            "U upper, L lower, D digit, S special (" + SPECIAL + "), O anything else",
            f"{PW_MIN}-{PW_MAX} characters, at least one U, L, D and S, nothing else",
            classify_password, pw["minimal"], password_rule,
            ["Srm@2026", "Trichy#Aiml5", "aB3$efgh", "Rush#2026Ab", "Qw1!Zx9&Lp"],
            ["srm@2026", "SRM@2026", "Srm@Trichy", "Srm20266", "Sr@1", "Srm @2026", "Abcdefg1!xyz9"],
            ["Cannot tell whether the password is common, leaked or equal to the user name (needs a list or the account record).",
             "Cannot check entropy or similarity to older passwords (needs history and a scoring function).",
             "NIST SP 800-63B advises against strict composition rules: length and a blocklist protect better.",
             "Rules such as 'no more than half of the characters are digits' need unbounded counting and are not regular."],
            extra=pw),
        "mobile": Validator(
            "mobile", "Mobile number",
            "'+' plus the digit classes 0, 1, 9, 2-5, 6-8; O anything else",
            "optional prefix +91, 91 or 0, then a 10-digit number starting with 6, 7, 8 or 9",
            classify_mobile, mob_min, mobile_rule,
            ["9876543210", "6000000000", "+919876543210", "919876543210", "09876543210", "9198765432", "8123456789"],
            ["5876543210", "987654321", "98765432101", "+91 9876543210", "+929876543210", "98765x3210", "915876543210"],
            ["Cannot tell whether the number is allocated, active or owned by this user (needs the operator or an OTP).",
             "The prefix '91' is ambiguous with a number that starts with 91, which is why the design needs an NFA.",
             "Landline numbers, STD codes and other countries need extra branches or a different language."],
            nfa=mob_nfa, extra={"subset": mob_sub, "minimal": mob_min}),
        "time": Validator(
            "time", "Time HH:MM (24-hour)",
            "digit classes 0-1, 2, 3, 4-5, 6-9, the colon ':' and O anything else",
            "hours 00-23, a colon, minutes 00-59",
            classify_time, time_dfa, time_rule,
            ["00:00", "09:30", "12:45", "19:05", "23:59"],
            ["24:00", "12:60", "7:30", "12-30", "1230", "23:5a"],
            ["Cannot tell whether the time slot is free or in the past (needs the calendar).",
             "Cannot handle time zones or daylight saving (needs a time library).",
             "A 12-hour format with AM/PM is a different language and needs extra states."],
            extra={}),
    }


APPS = build_all()
