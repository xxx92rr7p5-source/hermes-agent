"""1+4 体系 handoff 单测 — extract_handoff 5 case."""
from agent.handoff import extract_handoff


class TestExtractHandoff:
    """extract_handoff 5 用例覆盖."""

    def test_case1_changed_files_and_tests(self):
        """Case 1: stdout 含 changed_files + tests_run."""
        stdout = (
            "Files changed:\n"
            "- src/a.py\n"
            "- src/b.py\n"
            "\n"
            "Tests run:\n"
            "- test_x passed\n"
            "- test_y passed\n"
        )
        result = extract_handoff(stdout)
        assert result['changed_files'] == ['src/a.py', 'src/b.py']
        assert result['tests_run'] == ['test_x passed', 'test_y passed']
        assert result['decisions'] == []
        assert result['next_step'] == ''
        assert result['blocking_issues'] == []

    def test_case2_decisions_and_next_step_chinese(self):
        """Case 2: 中文格式 — 关键决策 + 下一步."""
        stdout = (
            "关键决策:\n"
            "- 用正则不用LLM\n"
            "- 异步优先\n"
            "\n"
            "下一步: code review by Reviewer agent\n"
        )
        result = extract_handoff(stdout)
        assert '用正则不用LLM' in result['decisions']
        assert '异步优先' in result['decisions']
        assert result['next_step'] == 'code review by Reviewer agent'

    def test_case3_tests_only(self):
        """Case 3: 只有 tests_run."""
        stdout = (
            "Tests run:\n"
            "- test_a\n"
            "- test_b\n"
            "- test_c\n"
        )
        result = extract_handoff(stdout)
        assert result['tests_run'] == ['test_a', 'test_b', 'test_c']
        assert result['changed_files'] == []

    def test_case4_empty_string(self):
        """Case 4: 空字符串 — 返回全空结构."""
        result = extract_handoff("")
        for key in ['changed_files', 'tests_run', 'decisions', 'blocking_issues']:
            assert result[key] == [], f"{key} should be empty list"
        assert result['next_step'] == ''

    def test_case5_none_input(self):
        """Case 5: None 输入 — 不抛异常，返回空结构."""
        result = extract_handoff(None)
        for key in ['changed_files', 'tests_run', 'decisions', 'blocking_issues']:
            assert result[key] == [], f"{key} should be empty list"
        assert result['next_step'] == ''
