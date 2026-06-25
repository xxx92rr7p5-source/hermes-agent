"""1+4 体系 D1+D2 Handoff 强制压缩.

从子 agent 的 stdout 提取结构化 handoff dict,
父 context 只收 handoff 摘要, 不收 raw stdout (25 号 §一 1.2, 22 号 §三 D1+D2).
"""

import re
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class Handoff:
    """子 agent 返回的 handoff 数据结构 (1+4 体系 8 段交接)."""
    changed_files: List[str] = field(default_factory=list)
    tests_run: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    next_step: str = ""
    blocking_issues: List[str] = field(default_factory=list)


# 中英双语正则模式 — 匹配子 agent 的结构化输出
_BULLET_PATTERNS = {
    'changed_files': [
        r'(?:files?\s*(?:created|modified|changed))\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:创建|修改|更改)(?:了)?(?:文件)?\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
    'tests_run': [
        r'(?:tests?\s*(?:run|executed|passed|failed))\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:测试|运行)(?:了)?\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
    'decisions': [
        r'(?:decisions?|key\s*decisions?)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:关键)?(?:决策|决定)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
    'blocking_issues': [
        r'(?:blocking\s*issues?|issues?\s*encountered)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:问题|阻塞)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
}

_NEXT_STEP_PATTERNS = [
    r'(?:next\s*steps?|下一步)\s*:\s*(.+?)(?:\n\n|\n\*|\n-|\n[A-Z]|\Z)',
]


def _extract_bullet_list(text: str, patterns: list) -> list:
    """从文本提取 bullet list 项."""
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if match:
            items = re.findall(r'[-*]\s*(.+)', match.group(1))
            return [item.strip() for item in items if item.strip()]
    return []


def _extract_single_line(text: str, patterns: list) -> str:
    """从文本提取单行值."""
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def extract_handoff(stdout) -> dict:
    """从子 agent stdout 提取结构化 handoff dict.

    Args:
        stdout: 子 agent 完整输出文本 (str) 或 None/非字符串

    Returns:
        dict: Handoff 结构 (可 JSON 序列化), 异常或空输入返回空结构.
        字段: changed_files, tests_run, decisions, next_step, blocking_issues
    """
    if not stdout or not isinstance(stdout, str):
        return asdict(Handoff())

    try:
        handoff = Handoff(
            changed_files=_extract_bullet_list(
                stdout, _BULLET_PATTERNS['changed_files']
            ),
            tests_run=_extract_bullet_list(
                stdout, _BULLET_PATTERNS['tests_run']
            ),
            decisions=_extract_bullet_list(
                stdout, _BULLET_PATTERNS['decisions']
            ),
            next_step=_extract_single_line(stdout, _NEXT_STEP_PATTERNS),
            blocking_issues=_extract_bullet_list(
                stdout, _BULLET_PATTERNS['blocking_issues']
            ),
        )
        return asdict(handoff)
    except Exception:
        return asdict(Handoff())
