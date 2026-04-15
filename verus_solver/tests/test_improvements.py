"""
Tests for the generalisation improvements:

* SlicePrecondStrategy  — variable-name agnostic, multi-slice detection
* StructuralLoopInvariantStrategy — while-loop frame
* SyntaxRepairStrategy  — compile-error recovery
* scorer.score_result   — progress-bonus logic
* triage.top_error_class — compile_error priority
"""

import pytest

from ..models import VerusIssue, VerusResult
from ..scorer import score_result
from ..strategies.slice_precond import SlicePrecondStrategy
from ..strategies.structural_loop_inv import StructuralLoopInvariantStrategy
from ..strategies.syntax_repair import SyntaxRepairStrategy
from ..triage import top_error_class


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(*, verified=0, errors=1, compile_error=False, issues=None) -> VerusResult:
    return VerusResult(
        success=False,
        verified=verified,
        errors=errors,
        compile_error=compile_error,
        raw_stdout="",
        raw_stderr="",
        issues=issues or [VerusIssue(kind="postcond", message="postcondition not satisfied")],
    )

def _compile_error_result() -> VerusResult:
    return VerusResult(
        success=False, verified=0, errors=0, compile_error=True,
        raw_stdout="", raw_stderr="error[E0308]: mismatched types",
        issues=[],
    )


# ===========================================================================
# SlicePrecondStrategy — variable-name agnostic
# ===========================================================================

FIRST_NEGATIVE = """\
pub fn first_negative(v: &[i32]) -> (result: i32) {
    for i in 0..v.len() {
        if v[i] < 0 { return i as i32; }
    }
    -1
}
"""

BINARY_SEARCH = """\
pub fn search(haystack: &[i32], needle: i32) -> usize {
    let mut lo = 0usize;
    let mut hi = haystack.len();
    lo
}
"""

TWO_SLICE_PARAMS = """\
pub fn zip_sum(a: &[u32], b: &[u32]) -> u64 {
    let mut s = 0u64;
    for i in 0..a.len() {
        s += a[i] as u64 + b[i] as u64;
    }
    s
}
"""

ALREADY_HAS_INVARIANT = """\
pub fn copy(src: &[i32], dst: &mut Vec<i32>) {
    for i in 0..src.len()
        invariant
            0 <= i <= src.len(),
    {
        dst.push(src[i]);
    }
}
"""


class TestSlicePrecondGeneralized:
    def test_fires_on_non_a_variable(self):
        s = SlicePrecondStrategy()
        cands = s.generate(FIRST_NEGATIVE, _result())
        assert len(cands) == 1, "Should fire on 'v' not just 'a'"
        assert "0 <= i <= v.len()" in cands[0].code

    def test_adds_length_equality_for_two_slices(self):
        s = SlicePrecondStrategy()
        cands = s.generate(TWO_SLICE_PARAMS, _result())
        assert len(cands) == 1
        assert "a.len() == b.len()" in cands[0].code

    def test_no_length_equality_for_single_slice(self):
        s = SlicePrecondStrategy()
        cands = s.generate(FIRST_NEGATIVE, _result())
        assert len(cands) == 1
        # There is no second slice parameter, so no length equality clause.
        assert "== v.len()" not in cands[0].code

    def test_no_fire_when_invariant_already_present(self):
        s = SlicePrecondStrategy()
        cands = s.generate(ALREADY_HAS_INVARIANT, _result())
        assert cands == [], "Must not double-inject when invariant already present"

    def test_preserves_function_body(self):
        s = SlicePrecondStrategy()
        cands = s.generate(FIRST_NEGATIVE, _result())
        assert "if v[i] < 0" in cands[0].code, "Body must be unchanged"


# ===========================================================================
# StructuralLoopInvariantStrategy
# ===========================================================================

MAX_EVEN = """\
pub fn max_even_indexed(a: &[i32]) -> (result: i32) {
    let mut m = a[0];
    let mut i = 2usize;
    while i < a.len() {
        if a[i] > m { m = a[i]; }
        i += 2;
    }
    m
}
"""

REVERSE_LOOP = """\
pub fn reverse(a: &mut [i32]) {
    let mut lo = 0usize;
    let mut hi = a.len() - 1;
    while lo < hi {
        let tmp = a[lo]; a[lo] = a[hi]; a[hi] = tmp;
        lo += 1; hi -= 1;
    }
}
"""

ALREADY_ANNOTATED_WHILE = """\
pub fn f(n: usize) {
    let mut i = 0usize;
    while i < n
        invariant
            0 <= i,
            i <= n,
        decreases n - i,
    {
        i += 1;
    }
}
"""


class TestStructuralLoopInvariantStrategy:
    def test_fires_on_while_i_lt_len(self):
        s = StructuralLoopInvariantStrategy()
        cands = s.generate(MAX_EVEN, _result())
        assert len(cands) == 1
        assert "invariant" in cands[0].code
        assert "0 <= i" in cands[0].code
        assert "i <= a.len()" in cands[0].code

    def test_fires_on_while_lo_lt_hi(self):
        s = StructuralLoopInvariantStrategy()
        cands = s.generate(REVERSE_LOOP, _result())
        assert len(cands) == 1
        assert "0 <= lo" in cands[0].code

    def test_also_adds_decreases(self):
        s = StructuralLoopInvariantStrategy()
        cands = s.generate(MAX_EVEN, _result())
        assert "decreases" in cands[0].code

    def test_no_fire_when_invariant_present(self):
        s = StructuralLoopInvariantStrategy()
        cands = s.generate(ALREADY_ANNOTATED_WHILE, _result())
        assert cands == [], "Must not inject invariant when one already exists"


# ===========================================================================
# SyntaxRepairStrategy
# ===========================================================================

SHADOWED_HI = """\
pub fn reverse(a: &mut [i32]) {
    let mut lo = 0usize;
    let mut hi = a.len() - 1;
    let n = a.len();
    while lo < hi {
        let hi = n - 1 - lo;
        let tmp = a[lo]; a[lo] = a[hi]; a[hi] = tmp;
        lo += 1;
    }
}
"""

IMMUTABLE_COUNTER = """\
pub fn count(n: usize) -> usize {
    let i = 0usize;
    while i < n {
        i += 1;
    }
    i
}
"""

NO_COMPILE_ERROR = """\
pub fn ok(a: &[i32]) -> i32 { a[0] }
"""


class TestSyntaxRepairStrategy:
    def test_no_fire_without_compile_error(self):
        s = SyntaxRepairStrategy()
        cands = s.generate(NO_COMPILE_ERROR, _result(compile_error=False))
        assert cands == [], "Must only fire on compile errors"

    def test_fires_on_compile_error(self):
        s = SyntaxRepairStrategy()
        cands = s.generate(SHADOWED_HI, _compile_error_result())
        # The outer `let mut hi` is present → inner `let hi` should become `hi =`
        assert len(cands) == 1
        assert "let hi = n - 1 - lo" not in cands[0].code
        assert "hi = n - 1 - lo" in cands[0].code

    def test_adds_mut_to_incremented_counter(self):
        s = SyntaxRepairStrategy()
        cands = s.generate(IMMUTABLE_COUNTER, _compile_error_result())
        assert len(cands) == 1
        assert "let mut i" in cands[0].code

    def test_no_candidate_when_nothing_to_fix(self):
        # Code compiles fine → should return [].
        s = SyntaxRepairStrategy()
        plain = "pub fn f() {}"
        cands = s.generate(plain, _compile_error_result())
        assert cands == []


# ===========================================================================
# score_result — progress bonus
# ===========================================================================

class TestRicherScoring:
    def _make(self, kinds, compile_error=False) -> VerusResult:
        return VerusResult(
            success=False, verified=0,
            errors=len(kinds), compile_error=compile_error,
            raw_stdout="", raw_stderr="",
            issues=[VerusIssue(kind=k, message="", line=i+1) for i, k in enumerate(kinds)],
        )

    def test_baseline_score_unchanged_without_prev(self):
        r = self._make(["postcond", "invariant"])
        assert score_result(r) == 0 * 100 - 2 * 150  # -300

    def test_kind_elimination_bonus(self):
        prev = self._make(["postcond", "overflow"])
        cur  = self._make(["postcond"])          # overflow eliminated
        s_no_prev = score_result(cur)
        s_with_prev = score_result(cur, prev=prev)
        assert s_with_prev > s_no_prev
        # +40 for eliminated kind ("overflow") + +20 for eliminated line (overflow on line 2)
        assert s_with_prev == s_no_prev + 40 + 20

    def test_line_elimination_bonus(self):
        prev = self._make(["postcond", "postcond"])   # two postcond on lines 1, 2
        cur  = self._make(["postcond"])               # one postcond on line 1
        s_with_prev = score_result(cur, prev=prev)
        s_no_prev   = score_result(cur)
        # Line 2 postcond is gone → +20
        assert s_with_prev == s_no_prev + 20

    def test_compile_error_penalty_dominates(self):
        r = self._make([], compile_error=True)
        assert score_result(r) < -5_000

    def test_kind_bonus_does_not_apply_without_prev(self):
        prev = self._make(["overflow"])
        cur  = self._make([])
        # Without prev argument, no bonus.
        assert score_result(cur) != score_result(cur, prev=prev)


# ===========================================================================
# triage — compile_error priority
# ===========================================================================

class TestTriageCompileError:
    def test_compile_error_takes_priority(self):
        result = VerusResult(
            success=False, verified=0, errors=2, compile_error=True,
            raw_stdout="", raw_stderr="error",
            issues=[VerusIssue(kind="postcond", message=""), VerusIssue(kind="invariant", message="")],
        )
        order = ["postcond", "invariant", "overflow"]
        assert top_error_class(result, order) == "compile_error"

    def test_normal_triage_when_no_compile_error(self):
        result = VerusResult(
            success=False, verified=0, errors=1, compile_error=False,
            raw_stdout="", raw_stderr="",
            issues=[VerusIssue(kind="invariant", message="")],
        )
        order = ["overflow", "invariant"]
        assert top_error_class(result, order) == "invariant"

    def test_returns_other_when_no_match(self):
        result = VerusResult(
            success=False, verified=0, errors=1, compile_error=False,
            raw_stdout="", raw_stderr="",
            issues=[VerusIssue(kind="decreases", message="")],
        )
        assert top_error_class(result, ["overflow"]) == "decreases"
