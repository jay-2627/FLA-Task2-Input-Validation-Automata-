"""Tests: listed examples plus cross-checks against an independent regex rule.

Run with:  python -m unittest -v      (or: python -m pytest -q)
"""
import itertools
import random
import unittest

from fa_validators.automata import DFA, NFA, TRAP, product
from fa_validators.validators import (APPS, SPECIAL, build_mobile_nfa, build_password, coverage_dfa,
                                      mobile_rule, password_rule, time_rule)

RNG = random.Random(2026)


def mutate(w, alphabet):
    w = list(w)
    kind = RNG.choice("ids")
    if kind == "i":
        w.insert(RNG.randrange(len(w) + 1), RNG.choice(alphabet))
    elif kind == "d" and w:
        w.pop(RNG.randrange(len(w)))
    elif w:
        w[RNG.randrange(len(w))] = RNG.choice(alphabet)
    return "".join(w)


def valid_password():
    n = RNG.randint(8, 12)
    chars = [RNG.choice("ABCXYZ"), RNG.choice("abcxyz"), RNG.choice("0123456789"), RNG.choice(SPECIAL)]
    pool = "ABCxyz0129" + SPECIAL
    chars += [RNG.choice(pool) for _ in range(n - 4)]
    RNG.shuffle(chars)
    return "".join(chars)


def valid_mobile():
    prefix = RNG.choice(["", "", "+91", "91", "0"])
    return prefix + RNG.choice("6789") + "".join(RNG.choice("0123456789") for _ in range(9))


def valid_time():
    return f"{RNG.randint(0, 23):02d}:{RNG.randint(0, 59):02d}"


GEN = {"password": (valid_password, "Aa1@#Zz9 "), "mobile": (valid_mobile, "0123456789+ a"),
       "time": (valid_time, "0123456789:a ")}
RULE = {"password": password_rule, "mobile": mobile_rule, "time": time_rule}


class ListedExamples(unittest.TestCase):
    def test_accepted_and_rejected_examples(self):
        for key, v in APPS.items():
            for w in v.accepted:
                self.assertTrue(v.check(w)[0], (key, w))
                self.assertTrue(RULE[key](w), (key, w))
            for w in v.rejected:
                self.assertFalse(v.check(w)[0], (key, w))
                self.assertFalse(RULE[key](w), (key, w))

    def test_at_least_five_each(self):
        for v in APPS.values():
            self.assertGreaterEqual(len(v.accepted), 5)
            self.assertGreaterEqual(len(v.rejected), 5)


class CrossChecks(unittest.TestCase):
    def test_mutated_strings_agree_with_regex(self):
        for key, v in APPS.items():
            gen, alpha = GEN[key]
            for _ in range(20000):
                w = gen()
                for _ in range(RNG.choice([0, 1, 2])):
                    w = mutate(w, alpha)
                self.assertEqual(v.check(w)[0], RULE[key](w), (key, w))

    def test_all_length_8_strings_over_small_alphabet_for_password(self):
        v = APPS["password"]
        for t in itertools.product("Aa1@", repeat=8):
            w = "".join(t)
            self.assertEqual(v.check(w)[0], password_rule(w), w)

    def test_exhaustive_time_strings_up_to_length_5(self):
        v = APPS["time"]
        for n in range(6):
            for t in itertools.product("0123:5a", repeat=n):
                w = "".join(t)
                self.assertEqual(v.check(w)[0], time_rule(w), w)


class Structure(unittest.TestCase):
    def test_password_state_counts(self):
        pw = build_password()
        self.assertEqual(pw["side_by_side"], 22)
        self.assertEqual(pw["product"].size(), 164)
        self.assertEqual(pw["minimal"].size(), 136)

    def test_minimal_dfa_equals_product_dfa(self):
        pw = build_password()
        for _ in range(20000):
            word = [RNG.choice(["U", "L", "D", "S", "O"]) for _ in range(RNG.randint(0, 14))]
            self.assertEqual(pw["product"].accepts_word(word), pw["minimal"].accepts_word(word))

    def test_mobile_nfa_subset_and_minimal_agree(self):
        nfa = build_mobile_nfa()
        sub, mini = nfa.to_dfa(), nfa.to_dfa().minimise()
        self.assertEqual(len(nfa.states()), 15)
        self.assertEqual(sub.size(), 24)
        self.assertEqual(mini.size(), 24)
        alpha = nfa.alphabet
        for _ in range(30000):
            word = [RNG.choice(alpha) for _ in range(RNG.randint(0, 13))]
            self.assertEqual(nfa.accepts_word(word), sub.accepts_word(word))
            self.assertEqual(nfa.accepts_word(word), mini.accepts_word(word))

    def test_prefix_91_is_really_ambiguous(self):
        # '9198765432' is a 10-digit number starting with 91, '919876543210' is prefix 91 + number
        v = APPS["mobile"]
        self.assertTrue(v.check("9198765432")[0])
        self.assertTrue(v.check("919876543210")[0])
        self.assertFalse(v.check("91987654321")[0])

    def test_time_dfa_is_minimal(self):
        self.assertEqual(APPS["time"].dfa.minimise().size(), APPS["time"].dfa.size())

    def test_coverage_dfa_has_16_states(self):
        self.assertEqual(coverage_dfa().size(), 16)

    def test_trap_is_absorbing(self):
        d = APPS["time"].dfa
        self.assertEqual(d.step(TRAP, "0-1"), TRAP)
        self.assertFalse(d.accepts_word(["O", "0-1", "0-1", ":", "0-1", "0-1"]))

    def test_complement(self):
        d = APPS["time"].dfa
        c = d.complement()
        for w in (["0-1", "0-1", ":", "0-1", "0-1"], ["O"], []):
            self.assertNotEqual(d.accepts_word(w), c.accepts_word(w))


if __name__ == "__main__":
    unittest.main()
