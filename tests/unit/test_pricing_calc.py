"""Tests for pricing.PricingManager — cost calculation and state."""
from __future__ import annotations

import pytest

from pricing import PricingManager


@pytest.fixture()
def pm():
    p = PricingManager()
    p._pricing = {"prompt_per_1m": 3.0, "completion_per_1m": 15.0}
    p._source = "openrouter_api"
    return p


def test_calc_cost_basic(pm):
    cost = pm.calc_cost(prompt_tokens=1000, completion_tokens=500)
    assert cost["input_cost_usd"] == pytest.approx(0.003)
    assert cost["output_cost_usd"] == pytest.approx(0.0075)
    assert cost["reasoning_cost_usd"] == 0.0
    assert cost["total_cost_usd"] == pytest.approx(0.0105)


def test_calc_cost_zero_tokens(pm):
    cost = pm.calc_cost(0, 0, 0)
    assert cost["total_cost_usd"] == 0.0


def test_calc_cost_reasoning_at_completion_rate(pm):
    cost = pm.calc_cost(0, 0, reasoning_tokens=1000)
    assert cost["reasoning_cost_usd"] == pytest.approx(0.015)


def test_calc_cost_total_equals_sum(pm):
    cost = pm.calc_cost(1000, 500, 200)
    expected = cost["input_cost_usd"] + cost["output_cost_usd"] + cost["reasoning_cost_usd"]
    assert cost["total_cost_usd"] == pytest.approx(expected)


@pytest.mark.parametrize("prompt,compl,reason", [
    (0, 0, 0),
    (1, 0, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1000000, 1000000, 1000000),
])
def test_calc_cost_all_values_non_negative(pm, prompt, compl, reason):
    cost = pm.calc_cost(prompt, compl, reason)
    for v in cost.values():
        assert v >= 0


def test_set_zero():
    pm = PricingManager()
    pm.set_zero()
    assert pm._source == "not_openrouter"
    assert pm._pricing["prompt_per_1m"] == 0.0


def test_is_loaded_initially_false():
    pm = PricingManager()
    assert pm.is_loaded is False


def test_is_loaded_after_set_zero():
    pm = PricingManager()
    pm.set_zero()
    assert pm.is_loaded is True
