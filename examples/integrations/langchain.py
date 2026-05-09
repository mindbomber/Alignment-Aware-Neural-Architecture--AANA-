"""AANA wrapper example for LangChain-style tools."""

from __future__ import annotations

import aana


class SearchPublicDocsTool:
    name = "search_public_docs"
    description = "Search public documentation."

    def invoke(self, payload: dict) -> dict:
        return {"results": [f"public docs result for {payload['query']}"]}


guarded_tool = aana.langchain_tool_middleware(SearchPublicDocsTool())


if __name__ == "__main__":
    result = guarded_tool.invoke({"query": "AANA Agent Action Contract v1"})
    decision = guarded_tool.aana_last_gate["result"]["architecture_decision"]
    print({"tool_result": result, "aana_route": decision["route"]})

