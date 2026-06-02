"""Planner: LLM output → a capped, cleaned list of sub-questions."""

from __future__ import annotations

from odr.agent.planner import FakePlanner, LLMPlanner
from odr.synthesise.fake_generator import FakeGenerator


def test_fake_planner_returns_fixed_list() -> None:
    assert FakePlanner(["a", "b"]).plan("anything") == ["a", "b"]


def test_llm_planner_parses_lines() -> None:
    gen = FakeGenerator("What contracts mention AI?\nWhat MoD announcements mention autonomy?")
    subs = LLMPlanner(gen).plan("AI and autonomy across UK defence?")
    assert subs == [
        "What contracts mention AI?",
        "What MoD announcements mention autonomy?",
    ]


def test_llm_planner_strips_bullets_blanks_and_caps_at_max() -> None:
    gen = FakeGenerator("1. a\n- b\n\n  c  \n* d\ne")
    subs = LLMPlanner(gen, max_subs=4).plan("q")
    assert subs == ["a", "b", "c", "d"]


def test_llm_planner_drops_lines_echoing_the_question() -> None:
    gen = FakeGenerator("the question\na real sub-question")
    assert LLMPlanner(gen).plan("the question") == ["a real sub-question"]
