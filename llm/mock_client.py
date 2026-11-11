"""
Deterministic Rule-Based Mock LLM Client.
Generates structured Markdown impact reports when running offline or without an API key.
"""
from typing import Optional
from core.models import ImpactSummary
from llm.base import BaseLLMClient


class MockLLMClient(BaseLLMClient):
    def generate_report(
        self,
        graph_context: str,
        diff_text: str,
        impact_summary: Optional[ImpactSummary] = None
    ) -> str:
        report: list[str] = []
        report.append("# Code Change Impact Analysis & Co-Change Recommendation Report")
        report.append("")
        report.append("> [!NOTE]")
        report.append("> Analysis generated using RepoGraph (ICLR 2025) k-hop Ego Subgraph Traversal.")
        report.append("")

        report.append("## 1. Executive Summary")
        report.append(
            "The analyzed Git diff modifies core repository logic. The k-hop dependency graph traversal "
            "identified downstream caller sites, dependent services, and unit test suites that are affected "
            "and require co-changes."
        )
        report.append("")

        report.append("## 2. Seed Code Modifications")
        if impact_summary and impact_summary.seed_nodes:
            for seed in impact_summary.seed_nodes:
                file = seed.get("file", "unknown")
                line = seed.get("line", 0)
                name = seed.get("name", "unknown")
                category = seed.get("category", "symbol")
                snippet = seed.get("snippet", "")
                report.append(f"- **File:** `{file}`")
                report.append(f"  - **Symbol:** `{name}` ({category.capitalize()}) at line {line}")
                if snippet:
                    report.append(f"  - **Snippet:** `{snippet}`")
        else:
            report.append("- Modified files detected in Git diff.")
        report.append("")

        report.append("## 3. Downstream Affected Components & Co-Change Recommendations")
        report.append(
            "> [!IMPORTANT]\n"
            "> Potentially impacted components are identified based on structural call paths, inheritance, "
            "> and historical couplings. Identification indicates components worth reviewing and verifying; "
            "> it does not automatically imply that code modifications are required."
        )
        report.append("")

        if impact_summary:
            idx = 1
            # 1-hop Direct Callers
            for caller in impact_summary.direct_callers:
                file = caller.get("file", "")
                line = caller.get("line", 0)
                name = caller.get("name", "")
                cat = caller.get("category", "symbol")
                report.append(f"### {idx}. `{file}`")
                report.append(f"- **Line:** {line}")
                report.append(f"- **Affected Symbol:** `{name}` ({cat})")
                report.append("- **Impact Category:** Direct Structural Impact (1-hop)")
                report.append("- **Reason:** Directly calls or overrides modified seed symbol.")
                report.append(f"- **Recommended Action:** Review call arguments or contract in `{name}` at line {line}.")
                report.append("- **Confidence Classification:** Confirmed High")
                report.append("")
                idx += 1

            # 2-hop Indirect Callers
            for caller in impact_summary.indirect_callers:
                file = caller.get("file", "")
                line = caller.get("line", 0)
                name = caller.get("name", "")
                cat = caller.get("category", "symbol")
                is_test = any(t in file.lower() for t in ("test", "spec", "check"))
                report.append(f"### {idx}. `{file}`")
                report.append(f"- **Line:** {line}")
                report.append(f"- **Affected Symbol:** `{name}` ({cat})")
                report.append(f"- **Impact Category:** {'Test Verification Suite' if is_test else 'Indirect Structural Impact (>= 2-hop)'}")
                report.append(f"- **Reason:** {'Contains assertions or test fixtures validating the changed code path.' if is_test else 'Depends transitively on upstream components consuming modified logic.'}")
                report.append(f"- **Recommended Action:** {'Execute and review test cases.' if is_test else 'Verify dataflow integration.'}")
                report.append(f"- **Confidence Classification:** {'Confirmed High' if is_test else 'Confirmed Medium'}")
                report.append("")
                idx += 1

            # Candidate Callers (Uncertain relationships)
            if impact_summary.candidate_callers:
                report.append("### Candidate Callers & Uncertain Relationships")
                for cand in impact_summary.candidate_callers:
                    file = cand.get("file", "")
                    line = cand.get("line", 0)
                    name = cand.get("name", "")
                    report.append(f"- `{name}` in `{file}:L{line}` (Ambiguous match / candidate reference; manual review recommended)")
                report.append("")

            # Suggested Relevant Tests (Test Impact Analysis)
            if impact_summary.test_recommendations:
                report.append("## 4. Test Impact Analysis (Suggested Relevant Tests)")
                report.append("The following test suites were identified as relevant to verify the code change:")
                for tr in impact_summary.test_recommendations:
                    tfile = tr.get("test_file", "")
                    tname = tr.get("test_name", "")
                    cls = tr.get("classification", "")
                    score = tr.get("impact_score", 0.0)
                    reason = tr.get("reason", "")
                    exec_flag = "Required" if tr.get("requires_execution", True) else "Recommended"
                    report.append(f"- **[{cls.upper()}]** `{tname}` (`{tfile}`)")
                    report.append(f"  - **Impact Score:** {score:.2f} | **Execution:** {exec_flag}")
                    report.append(f"  - **Evidence:** {reason}")
                report.append("")

            if idx == 1:
                report.append("No downstream caller files were directly affected within the k-hop subgraph.")
                report.append("")

        report.append("## 5. Verification & Testing Checklist")
        report.append("- [ ] Verify signature compatibility across all call sites.")
        report.append("- [ ] Execute directly related test suites identified in Test Impact Analysis.")
        report.append("- [ ] Review indirect downstream caller paths.")
        report.append("- [ ] Verify no uncommitted co-changed files are missing from the changeset.")

        return "\n".join(report)
