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
                report.append("- **Impact Category:** Direct Invocation Site (1-hop)")
                report.append("- **Reason:** Directly calls modified seed symbol whose behavior or signature changed.")
                report.append(f"- **Recommended Action:** Review call arguments in `{name}` at line {line} to align with new parameters.")
                report.append("- **Confidence:** High")
                report.append("")
                idx += 1

            # 2-hop Indirect / Test Callers
            for caller in impact_summary.indirect_callers:
                file = caller.get("file", "")
                line = caller.get("line", 0)
                name = caller.get("name", "")
                cat = caller.get("category", "symbol")
                is_test = any(t in file.lower() for t in ("test", "spec", "check"))
                report.append(f"### {idx}. `{file}`")
                report.append(f"- **Line:** {line}")
                report.append(f"- **Affected Symbol:** `{name}` ({cat})")
                report.append(f"- **Impact Category:** {'Test Suite / Assertions' if is_test else 'Indirect Downstream Caller (2-hop)'}")
                report.append(f"- **Reason:** {'Contains test cases or mocks validating the changed code path.' if is_test else 'Depends on upstream component affected by the modification.'}")
                report.append(f"- **Recommended Action:** {'Update test assertions and mock return values.' if is_test else 'Re-verify workflow integration and execute test suite.'}")
                report.append(f"- **Confidence:** {'High' if is_test else 'Medium'}")
                report.append("")
                idx += 1

            if idx == 1:
                report.append("No downstream caller files were directly affected within the k-hop subgraph.")
                report.append("")

        report.append("## 4. Verification & Testing Checklist")
        report.append("- [ ] Verify signature compatibility across all call sites.")
        report.append("- [ ] Run unit test suite for modified module and callers.")
        report.append("- [ ] Execute integration tests across affected components.")

        return "\n".join(report)
