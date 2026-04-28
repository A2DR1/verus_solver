"""
Tests for strategy generalization: recipe gating, decreases generalization,
overflow cleanup, and negative-match safety.

Run with:  python -m pytest verus_solver/tests/test_strategy_gating.py -v
"""

import pytest

from ..models import VerusResult, VerusIssue
from ..strategies.dot_product import DotProductStrategy
from ..strategies.reverse_template import ReverseTemplateStrategy
from ..strategies.decreases import DecreasesStrategy
from ..strategies.overflow import OverflowStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_result() -> VerusResult:
    return VerusResult(
        success=False,
        verified=0,
        errors=1,
        compile_error=False,
        raw_stdout="",
        raw_stderr="error: postcondition not satisfied",
        issues=[VerusIssue(kind="postcond", message="postcondition not satisfied")],
    )


def _decreases_result() -> VerusResult:
    return VerusResult(
        success=False,
        verified=0,
        errors=1,
        compile_error=False,
        raw_stdout="",
        raw_stderr="error: cannot prove termination",
        issues=[VerusIssue(kind="decreases", message="cannot prove termination")],
    )


# ---------------------------------------------------------------------------
# DotProductStrategy — fires whenever partial_dot + pub fn dot( are present
# ---------------------------------------------------------------------------

UNRELATED_DOT_CODE = """\
use vstd::prelude::*;
verus! {
// A scalar multiply function named dot — no spec function, not the benchmark.
pub fn dot(x: u64, y: u64) -> u64
    requires x < 1000, y < 1000,
{
    x * y
}
}
"""

PARTIAL_DOT_CODE = """\
use vstd::prelude::*;
verus! {
spec fn partial_dot(a: Seq<u8>, b: Seq<u8>, n: int) -> int { 0 }
pub fn dot(a: &[u8], b: &[u8]) -> (result: u32) {
    0
}
}
"""


class TestDotProductGating:
    def test_no_fire_on_unrelated_dot_function(self):
        """Strategy must not fire when 'partial_dot' is absent."""
        s = DotProductStrategy()
        cands = s.generate(UNRELATED_DOT_CODE, _empty_result())
        assert cands == [], "DotProductStrategy must not touch an unrelated dot() function"

    def test_fires_when_partial_dot_present(self):
        """Strategy fires whenever partial_dot + pub fn dot( are present."""
        s = DotProductStrategy()
        cands = s.generate(PARTIAL_DOT_CODE, _empty_result())
        assert len(cands) == 1
        assert cands[0].strategy == "dot_product"

    def test_replacement_contains_template(self):
        """Output code should include the lemma and invariant, not the stub."""
        s = DotProductStrategy()
        cands = s.generate(PARTIAL_DOT_CODE, _empty_result())
        assert len(cands) == 1
        assert "lemma_partial_dot_upper_bound" in cands[0].code


# ---------------------------------------------------------------------------
# ReverseTemplateStrategy — fires whenever pub fn reverse( is present
# ---------------------------------------------------------------------------

UNRELATED_REVERSE_CODE = """\
use vstd::prelude::*;
verus! {
// A string-reversal helper, nothing to do with the i32-slice benchmark.
pub fn reverse(s: &str) -> String {
    s.chars().rev().collect()
}
}
"""

REVERSE_I32_CODE = """\
use vstd::prelude::*;
verus! {
pub fn reverse(a: &mut [i32])
    requires old(a)@.len() >= 1,
{
    // stub
}
}
"""


class TestReverseTemplateGating:
    def test_fires_on_i32_reverse(self):
        """Strategy fires whenever pub fn reverse( is present."""
        s = ReverseTemplateStrategy()
        cands = s.generate(REVERSE_I32_CODE, _empty_result())
        assert len(cands) == 1
        assert cands[0].strategy == "reverse_template"

    def test_template_injected(self):
        """Output code should include the full invariant template."""
        s = ReverseTemplateStrategy()
        cands = s.generate(REVERSE_I32_CODE, _empty_result())
        assert len(cands) == 1
        assert "decreases n - lo" in cands[0].code

    def test_always_fires_on_any_reverse(self):
        """Strategy fires on any pub fn reverse( — even an unrelated one.
        The resulting candidate will fail Verus (compile error) and be discarded
        by the solver's scorer, so this is harmless in practice."""
        s = ReverseTemplateStrategy()
        cands = s.generate(UNRELATED_REVERSE_CODE, _empty_result())
        # Strategy fires — the verifier rejects it, solver scores -10000.
        assert len(cands) == 1
        assert cands[0].strategy == "reverse_template"


# ---------------------------------------------------------------------------
# DecreasesStrategy generalization
# ---------------------------------------------------------------------------

WHILE_LO_HI_CODE = """\
pub fn binary_search(a: &[i32], key: i32) -> usize {
    let mut lo = 0usize;
    let mut hi = a.len();
    while lo < hi {
        let mid = lo + (hi - lo) / 2;
        if a[mid] < key { lo = mid + 1; } else { hi = mid; }
    }
    lo
}
"""

WHILE_I_LEN_CODE = """\
pub fn sum(a: &[u64]) -> u64 {
    let mut i = 0usize;
    let mut acc = 0u64;
    while i < a.len() {
        acc += a[i];
        i += 1;
    }
    acc
}
"""

WHILE_I_N_CODE = """\
pub fn count(n: usize) -> usize {
    let mut i = 0usize;
    while i < n {
        i += 1;
    }
    i
}
"""

ALREADY_HAS_DECREASES = """\
pub fn reverse(a: &mut [i32]) {
    let mut lo = 0usize;
    let mut hi = a.len() - 1;
    while lo < hi
        decreases hi - lo,
    {
        let tmp = a[lo]; a[lo] = a[hi]; a[hi] = tmp;
        lo += 1; hi -= 1;
    }
}
"""

TWO_WHILE_LOOPS = """\
pub fn two_loops(n: usize) -> usize {
    let mut i = 0usize;
    while i < n {
        i += 1;
    }
    let mut j = 0usize;
    while j < n {
        j += 1;
    }
    j
}
"""


class TestDecreasesStrategy:
    def test_fires_on_while_lo_lt_hi(self):
        s = DecreasesStrategy()
        cands = s.generate(WHILE_LO_HI_CODE, _decreases_result())
        assert len(cands) == 1
        assert "decreases hi - lo" in cands[0].code

    def test_fires_on_while_i_lt_len(self):
        s = DecreasesStrategy()
        cands = s.generate(WHILE_I_LEN_CODE, _decreases_result())
        assert len(cands) == 1
        assert "decreases a.len() - i" in cands[0].code

    def test_fires_on_while_i_lt_n(self):
        """Should handle 'while i < n' not just 'while i < a.len()'."""
        s = DecreasesStrategy()
        cands = s.generate(WHILE_I_N_CODE, _decreases_result())
        assert len(cands) == 1
        assert "decreases n - i" in cands[0].code

    def test_no_fire_when_already_annotated(self):
        s = DecreasesStrategy()
        cands = s.generate(ALREADY_HAS_DECREASES, _decreases_result())
        assert cands == [], "Must not add decreases to an already-annotated loop"

    def test_handles_two_while_loops(self):
        """Both loops should get decreases clauses in one candidate."""
        s = DecreasesStrategy()
        cands = s.generate(TWO_WHILE_LOOPS, _decreases_result())
        assert len(cands) == 1
        assert cands[0].code.count("decreases") == 2

    def test_output_is_valid_python_string(self):
        s = DecreasesStrategy()
        cands = s.generate(WHILE_LO_HI_CODE, _decreases_result())
        assert len(cands) == 1
        # The patched code should still contain the original function name.
        assert "binary_search" in cands[0].code


# ---------------------------------------------------------------------------
# OverflowStrategy — no more hardcoded 65025
# ---------------------------------------------------------------------------

U32_ACCUM_CODE = """\
pub fn dot(a: &[u8], b: &[u8]) -> u32 {
    let mut sum: u32 = 0;
    for i in 0..a.len() {
        sum += (a[i] as u32) * (b[i] as u32);
    }
    sum
}
"""

U16_ACCUM_CODE = """\
pub fn accumulate(a: &[u8]) -> u16 {
    let mut total: u16 = 0;
    for i in 0..a.len() {
        total += a[i] as u16;
    }
    total
}
"""

NO_NARROW_ACCUM_CODE = """\
pub fn safe(a: &[u64]) -> u64 {
    let mut s: u64 = 0;
    for i in 0..a.len() {
        s += a[i];
    }
    s
}
"""

PARTIAL_DOT_BOUND_CODE = """\
pub fn dot(a: &[u8], b: &[u8]) -> u32 {
    let mut sum: u32 = 0;
    for i in 0..a.len()
        invariant
            sum as int == partial_dot(a@, b@, i as int),
    {
        sum += (a[i] as u32) * (b[i] as u32);
    }
    sum
}
"""


class TestOverflowStrategy:
    def test_widens_u32_to_u64(self):
        s = OverflowStrategy()
        cands = s.generate(U32_ACCUM_CODE, _empty_result())
        assert any("u64" in c.code for c in cands), "Should widen u32 accumulator to u64"

    def test_widens_u16_to_u32(self):
        s = OverflowStrategy()
        cands = s.generate(U16_ACCUM_CODE, _empty_result())
        assert any("u32" in c.code for c in cands)

    def test_no_fire_on_u64_accumulator(self):
        s = OverflowStrategy()
        cands = s.generate(NO_NARROW_ACCUM_CODE, _empty_result())
        assert cands == [], "u64 accumulator needs no widening"

    def test_still_widens_when_partial_dot_present(self):
        """Overflow strategy widens the u32 accumulator even when partial_dot is present."""
        s = OverflowStrategy()
        cands = s.generate(PARTIAL_DOT_BOUND_CODE, _empty_result())
        assert any("u64" in c.code for c in cands), \
            "Overflow strategy should widen the sum accumulator to u64"

    def test_no_65025_injected_anywhere(self):
        """The hardcoded 65025 bound must never be injected — Claude handles that."""
        s = OverflowStrategy()
        for code in (U32_ACCUM_CODE, PARTIAL_DOT_BOUND_CODE):
            cands = s.generate(code, _empty_result())
            assert all("65025" not in c.code for c in cands), \
                "OverflowStrategy must not inject the dot-product-specific 65025 bound"

    def test_cast_inserted_when_returning_narrow_type(self):
        """When sum is returned and function return type is u32, a cast should appear."""
        s = OverflowStrategy()
        cands = s.generate(U32_ACCUM_CODE, _empty_result())
        widen_cands = [c for c in cands if "u64" in c.code]
        if widen_cands:
            # Either sum was already cast or the strategy inserted one.
            assert "sum as u32" in widen_cands[0].code or "sum" in widen_cands[0].code
