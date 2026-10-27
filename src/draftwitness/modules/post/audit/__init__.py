"""Similarity auditor v0 (ADR 005): discount matches that are not plagiarism, and explain."""

from draftwitness.modules.post.audit.declarations import (
    Declarations,
    DeclarationsError,
    OwnWork,
    Template,
    load_declarations,
)
from draftwitness.modules.post.audit.engine import (
    AuditError,
    AuditResult,
    Discount,
    DiscountRule,
    Finding,
    FindingKind,
    InputFile,
    Method,
    audit,
)
from draftwitness.modules.post.audit.render import render_markdown
from draftwitness.modules.post.audit.rules import AuditRules, load_rules

__all__ = [
    "AuditError",
    "AuditResult",
    "AuditRules",
    "Declarations",
    "DeclarationsError",
    "Discount",
    "DiscountRule",
    "Finding",
    "FindingKind",
    "InputFile",
    "Method",
    "OwnWork",
    "Template",
    "audit",
    "load_declarations",
    "load_rules",
    "render_markdown",
]
