"""Tests for eval framework evaluators.

Tests code-based evaluators for:
- Edge cases (empty vs missing fields)
- Scoring consistency
- Error handling
"""

import pytest
from unittest.mock import MagicMock

from daily_digest.eval.expansion_evaluators import (
    structure_evaluator,
    efficiency_evaluator,
    sources_retrieved_evaluator,
)
from daily_digest.eval.langsmith_evaluators import (
    structure_evaluator_ls,
    efficiency_evaluator_ls,
    sources_retrieved_evaluator_ls,
    _collect_tool_calls_recursive,
    _format_trajectory_for_agentevals,
    _extract_fetched_content,
)


class TestStructureEvaluator:
    """Tests for structure_evaluator."""

    def test_all_fields_present(self):
        """Complete outputs should pass."""
        outputs = {
            "source_summary": "A summary",
            "key_points": ["point 1", "point 2"],
            "related": [{"url": "http://example.com", "title": "Example"}],
            "topics": ["topic-one"],
        }
        result = structure_evaluator({}, outputs)
        assert result["score"] == 1.0
        assert result["pass"] is True
        assert result["missing_fields"] == []

    def test_empty_lists_valid(self):
        """Empty lists should be valid (agent may produce no items)."""
        outputs = {
            "source_summary": "A summary",
            "key_points": [],  # Empty but present
            "related": [],
            "topics": [],
        }
        result = structure_evaluator({}, outputs)
        assert result["score"] == 1.0
        assert result["pass"] is True

    def test_empty_string_valid(self):
        """Empty string should be valid."""
        outputs = {
            "source_summary": "",  # Empty but present
            "key_points": [],
            "related": [],
            "topics": [],
        }
        result = structure_evaluator({}, outputs)
        assert result["score"] == 1.0
        assert result["pass"] is True

    def test_none_value_fails(self):
        """None value should fail."""
        outputs = {
            "source_summary": None,  # None should fail
            "key_points": [],
            "related": [],
            "topics": [],
        }
        result = structure_evaluator({}, outputs)
        assert result["score"] == 0.0
        assert result["pass"] is False
        assert "source_summary" in result["missing_fields"]

    def test_missing_field_fails(self):
        """Missing field should fail."""
        outputs = {
            "source_summary": "A summary",
            "key_points": [],
            # "related" is missing
            "topics": [],
        }
        result = structure_evaluator({}, outputs)
        assert result["score"] == 0.0
        assert result["pass"] is False
        assert "related" in result["missing_fields"]


class TestEfficiencyEvaluator:
    """Tests for efficiency_evaluator."""

    def _mock_run_with_tools(self, tool_names: list[str]) -> MagicMock:
        """Create mock run with tool calls."""
        run = MagicMock()
        child_runs = []
        for name in tool_names:
            tc = MagicMock()
            tc.run_type = "tool"
            tc.name = name
            tc.inputs = {}
            child_runs.append(tc)
        run.child_runs = child_runs
        return run

    def test_no_child_runs_returns_error(self):
        """Missing child_runs should return error."""
        run = MagicMock()
        run.child_runs = None
        result = efficiency_evaluator_ls(run, None)
        assert result["score"] is None
        assert "error" in result

    def test_no_tool_calls_neutral_score(self):
        """No tool calls should return 0.5 (neutral)."""
        run = MagicMock()
        run.child_runs = []
        result = efficiency_evaluator_ls(run, None)
        assert result["score"] == 0.5
        assert result["tool_calls"] == 0

    def test_unique_calls_perfect_score(self):
        """All unique tool calls should score 1.0."""
        run = self._mock_run_with_tools(["fetch_url", "web_search", "github_repo"])
        # Set different URLs
        run.child_runs[0].inputs = {"url": "http://a.com"}
        run.child_runs[1].inputs = {}
        run.child_runs[2].inputs = {"owner": "test", "repo": "repo"}
        result = efficiency_evaluator_ls(run, None)
        assert result["score"] == 1.0
        assert result["redundant"] == 0

    def test_redundant_calls_penalized(self):
        """Duplicate URL fetches should be penalized."""
        run = self._mock_run_with_tools(["fetch_url", "fetch_url"])
        run.child_runs[0].inputs = {"url": "http://same.com"}
        run.child_runs[1].inputs = {"url": "http://same.com"}
        result = efficiency_evaluator_ls(run, None)
        assert result["score"] < 1.0
        assert result["redundant"] == 1


class TestSourcesRetrievedEvaluator:
    """Tests for sources_retrieved_evaluator."""

    def _mock_run_with_tools(self, tool_names: list[str]) -> MagicMock:
        """Create mock run with tool calls."""
        run = MagicMock()
        child_runs = []
        for name in tool_names:
            tc = MagicMock()
            tc.run_type = "tool"
            tc.name = name
            tc.child_runs = None
            child_runs.append(tc)
        run.child_runs = child_runs
        return run

    def test_no_child_runs_returns_error(self):
        """Missing child_runs should return error."""
        run = MagicMock()
        run.child_runs = None
        result = sources_retrieved_evaluator_ls(run, None)
        assert result["score"] is None
        assert "error" in result

    def test_fetch_tool_passes(self):
        """Using fetch_url should pass."""
        run = self._mock_run_with_tools(["fetch_url"])
        result = sources_retrieved_evaluator_ls(run, None)
        assert result["score"] == 1.0
        assert result["pass"] is True

    def test_web_search_passes(self):
        """Using web_search should pass."""
        run = self._mock_run_with_tools(["web_search"])
        result = sources_retrieved_evaluator_ls(run, None)
        assert result["score"] == 1.0
        assert result["pass"] is True

    def test_github_repo_passes(self):
        """Using github_repo should pass."""
        run = self._mock_run_with_tools(["github_repo"])
        result = sources_retrieved_evaluator_ls(run, None)
        assert result["score"] == 1.0
        assert result["pass"] is True

    def test_no_fetch_tools_fails(self):
        """No fetch tools should fail."""
        run = self._mock_run_with_tools(["some_other_tool"])
        result = sources_retrieved_evaluator_ls(run, None)
        assert result["score"] == 0.0
        assert result["pass"] is False


class TestRecursiveToolCollection:
    """Tests for _collect_tool_calls_recursive."""

    def test_flat_tool_calls(self):
        """Direct tool calls should be collected."""
        tc1 = MagicMock(run_type="tool", name="fetch_url", child_runs=None)
        tc2 = MagicMock(run_type="tool", name="web_search", child_runs=None)
        child_runs = [tc1, tc2]

        result = _collect_tool_calls_recursive(child_runs)
        assert len(result) == 2

    def test_nested_tool_calls(self):
        """Nested tool calls (LangGraph style) should be collected."""
        # Simulate LangGraph: tools are nested inside "tools" chain runs
        inner_tool = MagicMock()
        inner_tool.run_type = "tool"
        inner_tool.child_runs = None

        tools_chain = MagicMock()
        tools_chain.run_type = "chain"
        tools_chain.child_runs = [inner_tool]

        agent_chain = MagicMock()
        agent_chain.run_type = "chain"
        agent_chain.child_runs = None

        child_runs = [agent_chain, tools_chain]

        result = _collect_tool_calls_recursive(child_runs)
        assert len(result) == 1
        assert result[0] is inner_tool

    def test_empty_child_runs(self):
        """Empty child_runs should return empty list."""
        result = _collect_tool_calls_recursive([])
        assert result == []

    def test_none_child_runs(self):
        """None child_runs should return empty list."""
        result = _collect_tool_calls_recursive(None)
        assert result == []


class TestTrajectoryFormatter:
    """Tests for _format_trajectory_for_agentevals."""

    def test_includes_tool_call_id(self):
        """Tool calls should have id, type, function fields."""
        tc = MagicMock()
        tc.run_type = "tool"
        tc.name = "fetch_url"
        tc.id = "abc123"
        tc.inputs = {"url": "http://example.com"}
        tc.outputs = {"content": "page content"}
        tc.child_runs = None

        run = MagicMock()
        run.inputs = {"content": "Test input"}
        run.child_runs = [tc]
        run.outputs = {}

        trajectory = _format_trajectory_for_agentevals(run)

        # Find assistant message with tool_calls
        assistant_msg = next(m for m in trajectory if m.get("tool_calls"))
        tool_call = assistant_msg["tool_calls"][0]

        assert "id" in tool_call
        assert tool_call["type"] == "function"
        assert "function" in tool_call

        # Find tool result message
        tool_msg = next(m for m in trajectory if m["role"] == "tool")
        assert "tool_call_id" in tool_msg
        assert tool_msg["tool_call_id"] == tool_call["id"]


class TestExtractFetchedContent:
    """Tests for _extract_fetched_content."""

    def test_extracts_fetch_url_content(self):
        """Should extract content from fetch_url outputs."""
        tc = MagicMock()
        tc.run_type = "tool"
        tc.name = "fetch_url"
        tc.outputs = {"content": "This is the fetched page content with enough text to pass the 50 char minimum."}
        tc.child_runs = None

        run = MagicMock()
        run.child_runs = [tc]

        result = _extract_fetched_content(run)
        assert len(result) == 1
        assert "fetch_url" in result[0]
        assert "fetched page content" in result[0]

    def test_truncates_long_content(self):
        """Should truncate content over 2000 chars."""
        tc = MagicMock()
        tc.run_type = "tool"
        tc.name = "fetch_url"
        tc.outputs = {"content": "x" * 3000}
        tc.child_runs = None

        run = MagicMock()
        run.child_runs = [tc]

        result = _extract_fetched_content(run)
        assert len(result) == 1
        assert "[truncated]" in result[0]
        assert len(result[0]) < 2100  # Should be truncated

    def test_skips_short_content(self):
        """Should skip content under 50 chars."""
        tc = MagicMock()
        tc.run_type = "tool"
        tc.name = "fetch_url"
        tc.outputs = {"content": "short"}
        tc.child_runs = None

        run = MagicMock()
        run.child_runs = [tc]

        result = _extract_fetched_content(run)
        assert len(result) == 0

    def test_ignores_non_fetch_tools(self):
        """Should ignore non-fetch tools."""
        tc = MagicMock()
        tc.run_type = "tool"
        tc.name = "some_other_tool"
        tc.outputs = {"content": "This is content from another tool that should be ignored by the extractor."}
        tc.child_runs = None

        run = MagicMock()
        run.child_runs = [tc]

        result = _extract_fetched_content(run)
        assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
