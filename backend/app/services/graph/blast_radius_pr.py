"""
Blast Radius PR Assessor Service

Parses a git unified diff, identifies the modified functions, queries
the Neo4j call graph for downstream impact, cross-references Documentation
records for risk factors (complexity, test coverage, security), and
generates a structured PRImpactReport with a Mermaid visual dependency tree.

Designed to run in a Celery worker triggered by the GitHub webhook on
pull_request (opened/synchronized) events.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.graph.blast_radius import calculate_blast_radius
from app.models.documentation import Documentation

logger = logging.getLogger(__name__)

# Risk thresholds
HIGH_COMPLEXITY_THRESHOLD = 7
CRITICAL_COMPLEXITY_THRESHOLD = 15


@dataclass
class AffectedFunction:
    function_name: str
    file_path: str
    function_id: Optional[str] = None
    cyclomatic_complexity: Optional[int] = None
    is_unprotected: bool = False
    handles_pii: bool = False
    has_embedding: bool = False
    risk_factors: List[str] = field(default_factory=list)
    individual_risk: str = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL


@dataclass
class PRImpactReport:
    repo_id: str
    modified_functions: List[str]
    affected_functions: List[AffectedFunction]
    risk_level: str              # Overall PR risk: LOW / MEDIUM / HIGH / CRITICAL
    affected_count: int
    untested_count: int          # Functions with no docstring (proxy for zero coverage)
    mermaid_markup: str
    summary_markdown: str
    raw_diff_lines: int = 0


def parse_diff_functions(diff_text: str) -> List[Dict[str, str]]:
    """
    Parses a unified git diff and extracts the names + file paths of
    modified functions.

    Strategy: Scan diff hunks for lines starting with '+' (additions) or
    lines in context that match common function definition patterns.
    Also extracts the filename from diff headers (--- a/... / +++ b/...).
    """
    modified: List[Dict[str, str]] = []

    # Python: def func_name( / async def func_name(
    py_func = re.compile(r"^[+\s]*(?:async\s+)?def\s+([a-zA-Z_]\w*)\s*\(")
    # JS/TS: function funcName( / const funcName = ( or =>
    js_func = re.compile(r"^[+\s]*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_]\w*)\s*\(")
    js_arrow = re.compile(r"^[+\s]*(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s+)?\(")
    # Java/Go/C#: return_type funcName( or public/private type funcName(
    jvm_func = re.compile(r"^[+\s]*(?:public|private|protected|static|async|void|int|str|bool|override)[\w\s<>]*\s+([a-zA-Z_]\w*)\s*\(")

    current_file = ""
    for line in diff_text.split("\n"):
        # Extract file name from diff header
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        if line.startswith("--- a/"):
            continue

        # Only look at added/changed lines
        if not (line.startswith("+") or line.startswith(" ")):
            continue

        func_name = None
        for pattern in [py_func, js_func, js_arrow, jvm_func]:
            m = pattern.match(line)
            if m:
                func_name = m.group(1)
                break

        if func_name and current_file:
            entry = {"function_name": func_name, "file_path": current_file}
            if entry not in modified:
                modified.append(entry)

    return modified


def _score_function_risk(doc: Optional[Documentation]) -> AffectedFunction:
    """Calculates per-function risk based on Documentation record fields."""
    if doc is None:
        return AffectedFunction(
            function_name="unknown",
            file_path="unknown",
            individual_risk="MEDIUM",
            risk_factors=["No documentation record found"]
        )

    factors = []
    risk = "LOW"

    cc = doc.cyclomatic_complexity or 0
    if cc >= CRITICAL_COMPLEXITY_THRESHOLD:
        risk = "CRITICAL"
        factors.append(f"Very high cyclomatic complexity ({cc})")
    elif cc >= HIGH_COMPLEXITY_THRESHOLD:
        risk = "HIGH" if risk != "CRITICAL" else risk
        factors.append(f"High cyclomatic complexity ({cc})")

    if doc.is_unprotected:
        risk = "HIGH" if risk not in ("CRITICAL",) else risk
        factors.append("Unprotected endpoint (no auth)")

    if doc.handles_pii:
        risk = "HIGH" if risk not in ("CRITICAL",) else risk
        factors.append("Handles PII data")

    if not doc.docstring:
        if risk == "LOW":
            risk = "MEDIUM"
        factors.append("No docstring (possible test coverage gap)")

    if doc.callers and len(doc.callers) > 10:
        if risk == "LOW":
            risk = "MEDIUM"
        factors.append(f"Highly coupled — called by {len(doc.callers)} functions")

    return AffectedFunction(
        function_name=doc.function_name,
        file_path=doc.file_path,
        function_id=str(doc.id),
        cyclomatic_complexity=doc.cyclomatic_complexity,
        is_unprotected=doc.is_unprotected,
        handles_pii=doc.handles_pii,
        has_embedding=getattr(doc, 'embedding', None) is not None,
        risk_factors=factors,
        individual_risk=risk
    )


def _generate_mermaid(
    modified_funcs: List[Dict[str, str]],
    affected_funcs: List[AffectedFunction]
) -> str:
    """
    Generates a Mermaid graph TD diagram showing the blast wave.
    Changed functions are styled in red; downstream in amber.
    """
    lines = ["graph TD"]
    seen_nodes = set()

    def node_id(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]", "_", name)

    for m in modified_funcs:
        nid = node_id(m["function_name"])
        if nid not in seen_nodes:
            lines.append(f'    {nid}["{m["function_name"]}\\n📄 {m["file_path"]}"]')
            lines.append(f"    style {nid} fill:#ff4444,color:#fff,stroke:#cc0000")
            seen_nodes.add(nid)

    for af in affected_funcs:
        nid = node_id(af.function_name)
        color = "#ff9900" if af.individual_risk in ("HIGH", "CRITICAL") else "#ffcc44"
        text_color = "#000"
        if nid not in seen_nodes:
            label = f"{af.function_name}"
            if af.cyclomatic_complexity:
                label += f"\\nCC:{af.cyclomatic_complexity}"
            if af.is_unprotected:
                label += "\\n🔓 Unprotected"
            lines.append(f'    {nid}["{label}"]')
            lines.append(f"    style {nid} fill:{color},color:{text_color},stroke:#996600")
            seen_nodes.add(nid)

        for m in modified_funcs:
            parent_id = node_id(m["function_name"])
            lines.append(f"    {parent_id} --> {nid}")

    return "\n".join(lines)


def _generate_summary(report_data: dict) -> str:
    """Generates the Markdown PR comment content."""
    risk_emoji = {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "🔴", "CRITICAL": "🚨"}
    emoji = risk_emoji.get(report_data["risk_level"], "⚠️")

    funcs_list = "\n".join(
        f"- `{f['function_name']}` in `{f['file_path']}` — **{f['individual_risk']}** risk"
        + (f" ({', '.join(f['risk_factors'][:2])})" if f.get("risk_factors") else "")
        for f in report_data["affected_functions"][:10]
    )
    if not funcs_list:
        funcs_list = "_No downstream functions affected._"

    modified_list = "\n".join(
        f"- `{m['function_name']}` in `{m['file_path']}`"
        for m in report_data.get("modified_functions_detail", [])[:5]
    )

    return f"""## 🔍 prime-pulsar Blast Radius Analysis

**Overall Risk Level:** {emoji} **{report_data['risk_level']}**
**Downstream Functions Affected:** {report_data['affected_count']}
**Functions with Coverage Gaps:** {report_data['untested_count']}

### Modified Functions
{modified_list or '_No functions detected in diff._'}

### Top Downstream Impact
{funcs_list}

### Visual Impact Tree
```mermaid
{report_data['mermaid_markup']}
```

> *Generated by [prime-pulsar](https://github.com/prime-pulsar) — Automated Codebase Intelligence*
"""


async def analyze_pr_diff(
    repo_id: str,
    diff_text: str,
    db: AsyncSession
) -> PRImpactReport:
    """
    Main entry point for PR analysis.
    1. Parses diff to find modified functions.
    2. Queries Neo4j blast radius for each function.
    3. Scores risk for each affected function.
    4. Generates Mermaid markup and Markdown summary.
    """
    modified_funcs = parse_diff_functions(diff_text)
    diff_lines = len(diff_text.split("\n"))

    if not modified_funcs:
        return PRImpactReport(
            repo_id=repo_id,
            modified_functions=[],
            affected_functions=[],
            risk_level="LOW",
            affected_count=0,
            untested_count=0,
            mermaid_markup='graph TD\n    A["No functions detected in diff"]',
            summary_markdown="No function-level changes detected in this diff.",
            raw_diff_lines=diff_lines
        )

    # Collect downstream affected function IDs from Neo4j
    all_affected_ids = set()
    for mf in modified_funcs:
        function_id = f"{repo_id}:{mf['file_path']}:{mf['function_name']}"
        try:
            affected_records = await calculate_blast_radius(function_id, depth=5)
            for rec in affected_records:
                all_affected_ids.add(rec.get("affected_function", ""))
        except Exception as e:
            logger.warning(f"Blast radius query failed for {function_id}: {e}")

    # Fetch Documentation DB records for affected functions
    affected_funcs: List[AffectedFunction] = []
    untested_count = 0

    if all_affected_ids:
        # Query by composite ID pattern: repo_id:file_path:func_name
        # We match by function_name and repository_id for efficiency
        func_names = [aid.split(":")[-1] for aid in all_affected_ids if aid]
        if func_names:
            stmt = select(Documentation).where(
                Documentation.repository_id == repo_id,
                Documentation.function_name.in_(func_names)
            )
            docs = (await db.execute(stmt)).scalars().all()

            for doc in docs:
                af = _score_function_risk(doc)
                if not doc.docstring:
                    untested_count += 1
                affected_funcs.append(af)

    # Calculate overall risk
    risk_levels = [af.individual_risk for af in affected_funcs]
    if "CRITICAL" in risk_levels:
        overall_risk = "CRITICAL"
    elif "HIGH" in risk_levels:
        overall_risk = "HIGH"
    elif "MEDIUM" in risk_levels:
        overall_risk = "MEDIUM"
    else:
        overall_risk = "LOW"

    # Sort by risk severity
    risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    affected_funcs.sort(key=lambda x: risk_order.get(x.individual_risk, 4))

    mermaid = _generate_mermaid(modified_funcs, affected_funcs)

    report_data = {
        "repo_id": repo_id,
        "risk_level": overall_risk,
        "affected_count": len(affected_funcs),
        "untested_count": untested_count,
        "affected_functions": [asdict(af) for af in affected_funcs],
        "modified_functions_detail": modified_funcs,
        "mermaid_markup": mermaid
    }
    summary_md = _generate_summary(report_data)

    return PRImpactReport(
        repo_id=repo_id,
        modified_functions=[m["function_name"] for m in modified_funcs],
        affected_functions=affected_funcs,
        risk_level=overall_risk,
        affected_count=len(affected_funcs),
        untested_count=untested_count,
        mermaid_markup=mermaid,
        summary_markdown=summary_md,
        raw_diff_lines=diff_lines
    )
