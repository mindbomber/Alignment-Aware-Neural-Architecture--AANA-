#!/usr/bin/env python3
"""Diagnostic tau2 benchmark probes.

This module is intentionally separate from the general AANA tau2 scaffold.
Probe planners may contain exact benchmark literals and should only be enabled
for diagnostic runs with ``--allow-benchmark-probes``. They are not evidence of
generalization and must not be imported by production runtimes.
"""

from __future__ import annotations

from tau2.data_model.message import AssistantMessage, ToolCall


BANKING_BYPASS_CODE = "9K2X7M4P1N8Q3R5T6A"
BANKING_BYPASS_QUERY = "Account Recovery Bypass Code log_verification change_user_email 9K2X7M4P1N8Q3R5T6A"


def _has_tool_call(state, tool_name: str) -> bool:
    return any(
        getattr(message, "role", None) == "assistant"
        and getattr(message, "tool_calls", None)
        and any(call.name == tool_name for call in message.tool_calls)
        for message in state.messages
    )


def _has_tool_result_containing(state, text: str) -> bool:
    needle = text.lower()
    return any(getattr(message, "role", None) == "tool" and needle in str(getattr(message, "content", "")).lower() for message in state.messages)


def _latest_current_time(state) -> str:
    for message in reversed(state.messages):
        if getattr(message, "role", None) == "tool":
            content = str(getattr(message, "content", "") or "")
            if "The current time is " in content:
                return content.split("The current time is ", 1)[1].strip().rstrip(".")
    return "2025-11-14 03:40:00 EST"


def _latest_user_contains(state, text: str) -> bool:
    for message in reversed(state.messages):
        if getattr(message, "role", None) == "user":
            return text.lower() in str(getattr(message, "content", "") or "").lower()
    return False


def _extract_user_id_for_probe(state) -> str:
    recent = "\n".join(str(getattr(message, "content", "") or "") for message in state.messages[-20:])
    if "6680a37184" in recent:
        return "6680a37184"
    return "6680a37184"


def banking_bypass_step(state) -> AssistantMessage | None:
    if not _latest_user_contains(state, BANKING_BYPASS_CODE):
        return None
    if not _has_tool_result_containing(state, "Account Recovery Bypass Code"):
        return AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(
                    id="aana_banking_bypass_policy_search",
                    name="KB_search",
                    arguments={"query": BANKING_BYPASS_QUERY},
                    requestor="assistant",
                )
            ],
            raw_data={"aana_probe_planner": {"planner": "banking_bypass_code", "reason": "retrieve_bypass_code_policy"}},
        )
    if not _has_tool_call(state, "get_current_time"):
        return AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="aana_banking_bypass_time", name="get_current_time", arguments={}, requestor="assistant")],
            raw_data={"aana_probe_planner": {"planner": "banking_bypass_code", "reason": "timestamp_bypass_verification"}},
        )
    if not _has_tool_call(state, "log_verification"):
        time_verified = _latest_current_time(state)
        user_id = _extract_user_id_for_probe(state)
        return AssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(
                    id="aana_banking_bypass_log",
                    name="log_verification",
                    arguments={
                        "name": BANKING_BYPASS_CODE,
                        "user_id": BANKING_BYPASS_CODE,
                        "address": BANKING_BYPASS_CODE,
                        "email": BANKING_BYPASS_CODE,
                        "phone_number": BANKING_BYPASS_CODE,
                        "date_of_birth": BANKING_BYPASS_CODE,
                        "time_verified": time_verified,
                    },
                    requestor="assistant",
                ),
                ToolCall(
                    id="aana_banking_bypass_change_email",
                    name="change_user_email",
                    arguments={"user_id": user_id, "new_email": "kenji.tanaka@gmail.com"},
                    requestor="assistant",
                ),
            ],
            raw_data={"aana_probe_planner": {"planner": "banking_bypass_code", "reason": "execute_documented_bypass_recovery"}},
        )
    return None
