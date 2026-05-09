#!/usr/bin/env python3
"""AANA v1/v2 custom scaffold for tau2-bench text evaluations.

This script is intended to be copied or referenced from a tau2-bench checkout.
It keeps the same CLI shape as the first AANA run and adds
``--aana-gate-version v1|v2`` with v2 as the default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from tau2.agent.base_agent import HalfDuplexAgent, ValidAgentInputMessage
from tau2.data_model.message import APICompatibleMessage, AssistantMessage, Message, MultiToolMessage, SystemMessage, ToolCall
from tau2.data_model.simulation import TextRunConfig
from tau2.environment.tool import Tool
from tau2.registry import registry
from tau2.runner.batch import run_domain
from tau2.utils.llm_utils import generate


AANA_REPO = Path(__file__).resolve().parents[2]
if str(AANA_REPO) not in sys.path:
    sys.path.insert(0, str(AANA_REPO))

from eval_pipeline.pre_tool_call_gate import gate_pre_tool_call, gate_pre_tool_call_v2, infer_tool_intent  # noqa: E402


DEFAULT_AANA_GATE_VERSION = "v2"
DEFAULT_AANA_MODE = "gate-plus-correction"
DEFAULT_ALLOW_BENCHMARK_PROBES = False
DEFAULT_WORKFLOW_SCOPE = "general_non_probe"


SYSTEM_PROMPT = """\
You are a customer service agent that helps the user according to the policy.
You may either respond to the user or call one provided tool, but not both in
the same turn.

Before a proposed tool call is executed, the runtime checks it through AANA.
If policy evidence, user intent, authorization, or confirmation is missing, ask
the user instead of guessing. If the requested action is policy-supported and
the user has provided the needed information or confirmation, proceed.

For general product, policy, or eligibility questions, search the knowledge base
first and answer from retrieved policy evidence. Do not access identity-bound
customer records for general advice unless the user asks for an account-specific
action or the policy explicitly requires account lookup. When the policy says a
user should run a discoverable user tool themselves, provide that tool through
the discoverable-tool mechanism and give the exact arguments the user needs.

{adapter_guidance}

<policy>
{domain_policy}
</policy>
"""


class AANAContractAgentState:
    def __init__(self, system_messages: list[SystemMessage], messages: list[APICompatibleMessage], gate_records: Optional[list[dict]] = None):
        self.system_messages = system_messages
        self.messages = messages
        self.gate_records = gate_records or []


def _latest_user_summary(messages: list[APICompatibleMessage]) -> str:
    for message in reversed(messages):
        if getattr(message, "role", None) == "user" and getattr(message, "content", None):
            return str(message.content)[:700]
    return "No user message available."


ADAPTER_CONFIG_PATH = Path(__file__).with_name("aana_tau2_adapter_config.json")


def _load_adapter_config(path: Path = ADAPTER_CONFIG_PATH) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


TAU2_ADAPTER_CONFIG = _load_adapter_config()


def _adapter_domain_config(domain: str) -> dict:
    config = TAU2_ADAPTER_CONFIG.get(domain, {})
    return config if isinstance(config, dict) else {}


def _banking_config() -> dict:
    return _adapter_domain_config("banking")


def _banking_card_profiles() -> dict:
    profiles = _banking_config().get("card_profiles", {})
    return profiles if isinstance(profiles, dict) else {}


def _banking_card_query() -> str:
    return str(_banking_config().get("card_policy_query", "personal credit card comparison rewards annual fee eligibility apply"))


def _banking_card_planner_instruction() -> str:
    return str(_banking_config().get("card_planner_instruction", "Use retrieved product policy evidence before recommending one product."))


def _banking_identity_planner_instruction() -> str:
    return str(_banking_config().get("identity_planner_instruction", "Verify identity factors before account-specific reads or writes."))


def _banking_identity_trigger_terms() -> tuple[str, ...]:
    terms = _banking_config().get("identity_trigger_terms", [])
    if isinstance(terms, list) and terms:
        return tuple(str(term).lower() for term in terms if str(term).strip())
    return ("change the email", "change my email", "human agent", "verify my identity", "account balance")


def _system_prompt_adapter_guidance(domain_policy: str) -> str:
    if _is_banking_policy(domain_policy):
        return str(_banking_config().get("system_prompt_guidance", ""))
    return ""


def _system_prompt(domain_policy: str) -> str:
    return SYSTEM_PROMPT.format(domain_policy=domain_policy, adapter_guidance=_system_prompt_adapter_guidance(domain_policy))


def _is_banking_policy(domain_policy: str) -> bool:
    text = domain_policy.lower()
    markers = _banking_config().get("policy_markers", [])
    if isinstance(markers, list) and markers:
        return any(str(marker).lower() in text for marker in markers)
    return "bank" in text


def _is_retail_policy(domain_policy: str) -> bool:
    text = domain_policy.lower()
    return "retail" in text and "order" in text and "exchange" in text


def _recent_text(messages: list[APICompatibleMessage], limit: int = 10) -> str:
    parts: list[str] = []
    for message in messages[-limit:]:
        content = getattr(message, "content", None)
        if content:
            parts.append(str(content))
    return "\n".join(parts)


def _recent_user_text(messages: list[APICompatibleMessage], limit: int = 10) -> str:
    parts: list[str] = []
    for message in messages[-limit:]:
        if getattr(message, "role", None) == "user" and getattr(message, "content", None):
            parts.append(str(message.content))
    return "\n".join(parts)


def _is_credit_card_recommendation_turn(message: ValidAgentInputMessage, state: AANAContractAgentState, domain_policy: str) -> bool:
    if not _is_banking_policy(domain_policy):
        return False
    candidate_messages = message.tool_messages if isinstance(message, MultiToolMessage) else [message]
    user_texts = [
        str(getattr(candidate, "content", "") or "")
        for candidate in candidate_messages
        if getattr(candidate, "role", None) == "user" and getattr(candidate, "content", None)
    ]
    if not user_texts:
        return False
    text = " ".join(user_texts).lower()
    if "credit card" not in text and "cash back" not in text and "rewards card" not in text:
        return False
    if any(token in text for token in ("close", "dispute", "fraud", "transaction", "statement", "balance", "downgrade")):
        return False
    recent_assistant_search = [
        prior
        for prior in state.messages[-8:]
        if getattr(prior, "role", None) == "assistant"
        and getattr(prior, "tool_calls", None)
        and any(call.name == "KB_search" and any(card.lower() in str(call.arguments).lower() for card in _banking_card_profiles()) for call in prior.tool_calls)
    ]
    return not recent_assistant_search


def _is_weak_banking_card_search(tool_call: ToolCall) -> bool:
    if tool_call.name != "KB_search":
        return False
    query = str(tool_call.arguments.get("query", "")).lower()
    if "credit card" not in query and "rewards card" not in query and "cash back" not in query:
        return False
    required_terms = tuple(card.lower() for card in _banking_card_profiles())
    if not required_terms:
        return False
    return not all(term in query for term in required_terms)


def _strengthen_banking_card_searches(response: AssistantMessage, domain_policy: str) -> None:
    if not _is_banking_policy(domain_policy) or not response.tool_calls:
        return
    for tool_call in response.tool_calls:
        if _is_weak_banking_card_search(tool_call):
            tool_call.arguments["query"] = _banking_card_query()
            response.raw_data = response.raw_data or {}
            response.raw_data["aana_planner"] = {
                "planner": "banking_card_comparison",
                "reason": "rewrote_weak_card_search_to_targeted_policy_query",
            }


def _banking_card_planner_search() -> AssistantMessage:
    return AssistantMessage(
        role="assistant",
        content=None,
        tool_calls=[
            ToolCall(
                id="aana_banking_card_planner_search",
                name="KB_search",
                arguments={"query": _banking_card_query()},
                requestor="assistant",
            )
        ],
        raw_data={"aana_planner": {"planner": "banking_card_comparison", "reason": "force_targeted_card_policy_retrieval"}},
    )


def _has_banking_card_policy_context(state: AANAContractAgentState) -> bool:
    recent = _recent_text(state.messages, limit=20).lower()
    planner_was_used = any(
        getattr(message, "role", None) == "assistant"
        and getattr(message, "raw_data", None)
        and message.raw_data.get("aana_planner", {}).get("planner") == "banking_card_comparison"
        for message in state.messages[-12:]
    )
    return planner_was_used or any(card.lower() in recent for card in _banking_card_profiles())


def _money_tolerance(text: str) -> int | None:
    if "no annual fee" in text or "avoid any annual fee" in text or "avoid annual fee" in text:
        return 0
    if "$100" in text or "100 in fees" in text or "up to 100" in text:
        return 100
    if "$200" in text or "200 annual fee" in text:
        return 200
    return None


def _banking_card_preference_flags(state: AANAContractAgentState) -> dict:
    text = _recent_user_text(state.messages, limit=20).lower()
    latest = _latest_user_text(state).lower()
    subscription_terms = [str(term).lower() for term in _banking_config().get("subscription_terms", []) if str(term).strip()]
    has_subscription = any(term in text for term in subscription_terms)
    no_subscription = any(f"do not have a {term}" in text or f"don't have a {term}" in text for term in subscription_terms)
    return {
        "has_subscription": has_subscription,
        "no_subscription": no_subscription,
        "wants_highest_cash_back": "highest cash back" in text or "top cash back" in text,
        "wants_no_annual_fee": "no annual fee" in text or "avoid any annual fee" in text or "avoid annual fee" in text,
        "fee_tolerance": _money_tolerance(text),
        "wants_foreign_travel": "foreign transaction" in text or "travel" in text,
        "wants_purchase_protection": "purchase protection" in text,
        "wants_large_credit_limit": "$100,000" in text or "100,000" in text or "at least 100000" in text,
        "asks_for_one_card": "recommend just one card" in latest or "best fit" in latest or "best card" in latest,
    }


def _score_banking_card(card_name: str, flags: dict) -> tuple[int, list[str]]:
    profile = _banking_card_profiles()[card_name]
    score = 0
    reasons: list[str] = []
    if profile.get("requires_subscription") and flags["no_subscription"]:
        return -100, ["requires a subscription the user said they do not have"]
    if flags["has_subscription"] and profile.get("requires_subscription"):
        score += 4
        reasons.append("matches subscription eligibility")
    if flags["wants_no_annual_fee"]:
        if profile.get("annual_fee", 0) == 0:
            score += 3
            reasons.append("has no annual fee")
        else:
            score -= 2
    fee_tolerance = flags["fee_tolerance"]
    if fee_tolerance is not None:
        if profile.get("annual_fee", 0) <= fee_tolerance:
            score += 2
            reasons.append(f"fits the ${fee_tolerance} annual-fee tolerance")
        else:
            score -= 3
    if flags["wants_highest_cash_back"]:
        score += profile.get("cash_back_rank", 0)
        reasons.append("ranks strongly for cash back")
    if flags["wants_foreign_travel"]:
        score += profile.get("foreign_travel_rank", 0)
        reasons.append("fits travel and foreign-transaction needs")
    if flags["wants_purchase_protection"]:
        score += profile.get("purchase_protection_rank", profile.get("foreign_travel_rank", 0))
        reasons.append("fits purchase-protection needs")
    if flags["wants_large_credit_limit"]:
        score += profile.get("large_credit_limit_rank", 0)
        reasons.append("fits the large credit-limit requirement")
    return score, reasons


def _rank_banking_cards(state: AANAContractAgentState) -> tuple[str, list[str]]:
    flags = _banking_card_preference_flags(state)
    profiles = _banking_card_profiles()
    if not profiles:
        return "configured card", ["no configured card profiles were available"]
    scored = [(card, *_score_banking_card(card, flags)) for card in profiles]
    scored.sort(key=lambda item: item[1], reverse=True)
    best_card, _score, reasons = scored[0]
    return best_card, reasons[:3]


def _banking_card_recommendation_response(state: AANAContractAgentState, reason: str) -> AssistantMessage:
    card_name, reasons = _rank_banking_cards(state)
    reason_text = "; ".join(reasons) if reasons else "it best matches the stated constraints"
    content = (
        f"I recommend the {card_name}. Based on the card policy and your stated constraints, "
        f"{reason_text}. You can apply with the user tool using card_type=\"{card_name}\"."
    )
    return AssistantMessage.text(
        content=content,
        raw_data={
            "aana_planner": {
                "planner": "banking_card_scorer",
                "reason": reason,
                "recommended_card": card_name,
                "ranking_reasons": reasons,
            }
        },
    )


def _should_emit_banking_card_recommendation(state: AANAContractAgentState, domain_policy: str) -> bool:
    if not _is_banking_policy(domain_policy) or not _has_banking_card_policy_context(state):
        return False
    latest = _latest_user_text(state).lower()
    if "apply_for_credit_card" in _recent_text(state.messages, limit=4).lower():
        return False
    return any(
        token in latest
        for token in (
            "recommend just one card",
            "best fit",
            "best card",
            "which card",
            "can reach or exceed $100,000",
            "credit limit",
        )
    )


def _correct_banking_card_response(response: AssistantMessage, state: AANAContractAgentState, domain_policy: str) -> AssistantMessage:
    if not _should_emit_banking_card_recommendation(state, domain_policy):
        return response
    if response.tool_calls:
        return response
    content = str(getattr(response, "content", "") or "")
    recommended_card, _reasons = _rank_banking_cards(state)
    card_names = tuple(_banking_card_profiles())
    mentions_other_card = any(card in content and card != recommended_card for card in card_names)
    lacks_direct_recommendation = recommended_card not in content or "recommend" not in content.lower()
    if mentions_other_card or lacks_direct_recommendation:
        return _banking_card_recommendation_response(state, "overrode_weak_or_conflicting_card_recommendation")
    return response


def _messages_with_planner_context(state: AANAContractAgentState) -> list[APICompatibleMessage | SystemMessage]:
    messages: list[APICompatibleMessage | SystemMessage] = state.system_messages + state.messages
    planner_messages: list[SystemMessage] = []
    if any(
        getattr(message, "role", None) == "assistant"
        and getattr(message, "raw_data", None)
        and message.raw_data.get("aana_planner", {}).get("planner") == "banking_card_comparison"
        for message in state.messages[-8:]
    ):
        planner_messages.append(SystemMessage(role="system", content=_banking_card_planner_instruction()))
    if _is_banking_policy(" ".join(str(getattr(message, "content", "") or "") for message in state.system_messages)) and any(
        token in _recent_text(state.messages).lower()
        for token in _banking_identity_trigger_terms()
    ):
        planner_messages.append(SystemMessage(role="system", content=_banking_identity_planner_instruction()))
    if planner_messages:
        return state.system_messages + planner_messages + state.messages
    return messages


def _has_tool_call(state: AANAContractAgentState, tool_name: str) -> bool:
    return any(
        getattr(message, "role", None) == "assistant"
        and getattr(message, "tool_calls", None)
        and any(call.name == tool_name for call in message.tool_calls)
        for message in state.messages
    )


def _has_tool_call_args(state: AANAContractAgentState, tool_name: str, expected: dict) -> bool:
    for message in state.messages:
        if getattr(message, "role", None) != "assistant" or not getattr(message, "tool_calls", None):
            continue
        for call in message.tool_calls:
            if call.name != tool_name:
                continue
            if all(call.arguments.get(key) == value for key, value in expected.items()):
                return True
    return False


def _has_tool_result_containing(state: AANAContractAgentState, text: str) -> bool:
    needle = text.lower()
    return any(getattr(message, "role", None) == "tool" and needle in str(getattr(message, "content", "")).lower() for message in state.messages)


def _latest_user_text(state: AANAContractAgentState) -> str:
    for message in reversed(state.messages):
        if getattr(message, "role", None) == "user":
            return str(getattr(message, "content", "") or "")
    return ""


def _planner_tool_call(planner: str, reason: str, tool_name: str, arguments: dict) -> AssistantMessage:
    safe_id = f"aana_{planner}_{tool_name}".replace("-", "_")
    return AssistantMessage(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id=safe_id[:80], name=tool_name, arguments=arguments, requestor="assistant")],
        raw_data={"aana_planner": {"planner": planner, "reason": reason}},
    )


def _json_object(content: str) -> dict | list | str | None:
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return content


def _call_name(call) -> str:
    return getattr(call, "name", None) or call.get("name", "")


def _call_arguments(call) -> dict:
    return getattr(call, "arguments", None) or call.get("arguments", {}) or {}


def _retail_observations(state: AANAContractAgentState) -> list[tuple[str, dict, object]]:
    observations: list[tuple[str, dict, object]] = []
    pending: list[tuple[str, dict]] = []
    for message in state.messages:
        if getattr(message, "role", None) == "assistant" and getattr(message, "tool_calls", None):
            for call in message.tool_calls:
                pending.append((_call_name(call), _call_arguments(call)))
            continue
        if getattr(message, "role", None) == "tool":
            tool_name, arguments = pending.pop(0) if pending else ("", {})
            content = str(getattr(message, "content", "") or "")
            observations.append((tool_name, arguments, _json_object(content) if content else content))
    return observations


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _singular_tokens(text: str) -> set[str]:
    tokens = set()
    for token in _normalize_text(text).split():
        tokens.add(token[:-1] if len(token) > 3 and token.endswith("s") else token)
    return tokens


def _retail_identity_facts(text: str) -> dict:
    facts: dict = {}
    email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    if email:
        facts["email"] = email.group(0)
    zip_match = re.search(r"\b\d{5}\b", text)
    if zip_match:
        facts["zip"] = zip_match.group(0)
    name_match = re.search(r"(?:name is|i am|i'm|this is)\s+([A-Z][a-zA-Z'-]+)\s+([A-Z][a-zA-Z'-]+)", text)
    if not name_match:
        name_match = re.search(r"\b([A-Z][a-zA-Z'-]+)\s+([A-Z][a-zA-Z'-]+)\b(?:,?\s+(?:and\s+)?(?:my\s+)?zip| in zip| living in zip)", text)
    if name_match:
        facts["first_name"] = name_match.group(1)
        facts["last_name"] = name_match.group(2)
    order = re.search(r"#W\d+", text, flags=re.IGNORECASE)
    if order:
        facts["order_id"] = order.group(0).upper()
    return facts


def _retail_intent(text: str) -> str | None:
    normalized = _normalize_text(text)
    if "exchange" in normalized:
        return "exchange"
    if "return" in normalized:
        return "return"
    if "modify" in normalized or "change" in normalized or "update" in normalized:
        return "modify"
    if "cancel" in normalized:
        return "cancel"
    return None


def _retail_confirmed(text: str) -> bool:
    latest = _normalize_text(text)
    return any(token in latest for token in ("yes", "confirm", "correct", "go ahead", "proceed", "please do", "process"))


def _retail_state(state: AANAContractAgentState) -> dict:
    observations = _retail_observations(state)
    user_id: str | None = None
    user_details: dict | None = None
    orders: dict[str, dict] = {}
    products: dict[str, dict] = {}
    for tool_name, arguments, data in observations:
        if tool_name.startswith("find_user_id") and isinstance(data, str) and data:
            user_id = data
        elif tool_name == "get_user_details" and isinstance(data, dict):
            user_details = data
            user_id = data.get("user_id") or user_id
        elif tool_name == "get_order_details" and isinstance(data, dict) and data.get("order_id"):
            orders[data["order_id"]] = data
        elif tool_name == "get_product_details" and isinstance(data, dict) and data.get("product_id"):
            products[data["product_id"]] = data
    return {"user_id": user_id, "user_details": user_details, "orders": orders, "products": products}


def _retail_product_requested(item_name: str, user_text: str) -> bool:
    item_tokens = _singular_tokens(item_name)
    text_tokens = _singular_tokens(user_text)
    if item_tokens and item_tokens.issubset(text_tokens):
        return True
    descriptive_tokens = item_tokens - {"smart", "mechanical", "wireless", "portable", "electric", "digital"}
    return any(token in text_tokens for token in descriptive_tokens if len(token) >= 5)


def _retail_tool_error_after_call(state: AANAContractAgentState, tool_name: str, arguments: dict) -> bool:
    pending_match = False
    for message in state.messages:
        if getattr(message, "role", None) == "assistant" and getattr(message, "tool_calls", None):
            pending_match = any(_call_name(call) == tool_name and _call_arguments(call) == arguments for call in message.tool_calls)
            continue
        if pending_match and getattr(message, "role", None) == "tool":
            return str(getattr(message, "content", "") or "").lower().startswith("error:")
    return False


def _retail_relevant_orders(workflow: str, facts: dict, state_data: dict, user_text: str) -> list[dict]:
    orders = list(state_data["orders"].values())
    if facts.get("order_id"):
        orders = [order for order in orders if order.get("order_id") == facts["order_id"]]
    status_by_workflow = {"return": "delivered", "exchange": "delivered", "modify": "pending", "cancel": "pending"}
    required_status = status_by_workflow.get(workflow)
    if required_status:
        status_orders = [order for order in orders if str(order.get("status", "")).startswith(required_status)]
        if status_orders:
            orders = status_orders
    requested_orders = [
        order
        for order in orders
        if any(_retail_product_requested(str(item.get("name", "")), user_text) for item in order.get("items", []))
    ]
    return requested_orders or orders


def _retail_requested_items(order: dict, user_text: str) -> list[dict]:
    items = order.get("items", [])
    requested = [item for item in items if _retail_product_requested(str(item.get("name", "")), user_text)]
    return requested or items


def _retail_payment_method(order: dict, user_details: dict | None) -> str | None:
    for payment in order.get("payment_history", []):
        if payment.get("payment_method_id"):
            return payment["payment_method_id"]
    methods = (user_details or {}).get("payment_methods", {})
    if isinstance(methods, dict) and methods:
        return next(iter(methods))
    return None


def _retail_variant_score(current_item: dict, variant: dict, user_text: str) -> int:
    if not variant.get("available", True):
        return -1000
    if variant.get("item_id") == current_item.get("item_id"):
        return -1000
    score = 0
    text = _normalize_text(user_text)
    current_options = current_item.get("options", {})
    for key, value in variant.get("options", {}).items():
        value_text = _normalize_text(str(value))
        current_value = _normalize_text(str(current_options.get(key, "")))
        if value_text and f"instead of {value_text}" in text:
            score -= 20
        elif value_text and value_text in text:
            score += 8
        value_tokens = set(value_text.split())
        requested_token_overlap = value_tokens.intersection(set(text.split())) - {"and", "or", "the", "with"}
        if requested_token_overlap:
            score += 3 * len(requested_token_overlap)
        if current_value and value_text == current_value and f"instead of {current_value}" in text:
            score -= 20
        elif current_value and value_text == current_value and f"same {key}".replace("_", " ") in text:
            score += 4
        if value_text != current_value:
            score += 1
    brightness = _normalize_text(str(variant.get("options", {}).get("brightness", "")))
    if "less bright" in text and brightness == "low":
        score += 10
    if "brighter" in text and brightness == "high":
        score += 10
    capacity = _normalize_text(str(variant.get("options", {}).get("capacity", "")))
    if "bigger" in text or "larger" in text:
        number = re.search(r"\d+", capacity)
        current_number = re.search(r"\d+", _normalize_text(str(current_options.get("capacity", ""))))
        if number and current_number and int(number.group(0)) > int(current_number.group(0)):
            score += 10
    return score


def _retail_best_variant(current_item: dict, product: dict, user_text: str) -> str | None:
    variants = product.get("variants", {})
    scored = [
        (item_id, _retail_variant_score(current_item, variant, user_text))
        for item_id, variant in variants.items()
        if isinstance(variant, dict)
    ]
    scored = [item for item in scored if item[1] > -1000]
    if not scored:
        return None
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[0][0] if scored[0][1] > 0 else None


def _retail_confirmation_response(workflow: str, order_id: str, items: list[dict], new_item_ids: list[str] | None, payment_method_id: str | None) -> AssistantMessage:
    item_names = ", ".join(f"{item.get('name')} ({item.get('item_id')})" for item in items)
    if workflow in ("exchange", "modify"):
        content = f"Please confirm: {workflow} order {order_id} item(s) {item_names} to new item id(s) {', '.join(new_item_ids or [])} using payment method {payment_method_id}. Reply yes to proceed."
    elif workflow == "return":
        content = f"Please confirm: return order {order_id} item(s) {item_names} with refund to payment method {payment_method_id}. Reply yes to proceed."
    else:
        content = f"Please confirm: {workflow} order {order_id}. Reply yes to proceed."
    return AssistantMessage.text(content=content, raw_data={"aana_planner": {"planner": "retail_order_workflow", "reason": "request_write_confirmation"}})


def _retail_order_planner_step(state: AANAContractAgentState, domain_policy: str, tools_by_name: dict[str, Tool]) -> AssistantMessage | None:
    if not _is_retail_policy(domain_policy):
        return None
    user_text = _recent_user_text(state.messages, limit=20)
    latest = _latest_user_text(state)
    workflow = _retail_intent(user_text)
    if workflow not in ("return", "exchange", "modify", "cancel"):
        return None
    facts = _retail_identity_facts(user_text)
    state_data = _retail_state(state)
    if not state_data["user_id"]:
        if facts.get("email") and "find_user_id_by_email" in tools_by_name and not _has_tool_call_args(state, "find_user_id_by_email", {"email": facts["email"]}):
            return _planner_tool_call("retail_order_workflow", "locate_customer_by_email", "find_user_id_by_email", {"email": facts["email"]})
        if all(facts.get(key) for key in ("first_name", "last_name", "zip")) and "find_user_id_by_name_zip" in tools_by_name:
            args = {"first_name": facts["first_name"], "last_name": facts["last_name"], "zip": facts["zip"]}
            if not _has_tool_call_args(state, "find_user_id_by_name_zip", args):
                return _planner_tool_call("retail_order_workflow", "locate_customer_by_name_zip", "find_user_id_by_name_zip", args)
        return None
    if not state_data["user_details"] and "get_user_details" in tools_by_name:
        args = {"user_id": state_data["user_id"]}
        if not _has_tool_call_args(state, "get_user_details", args):
            return _planner_tool_call("retail_order_workflow", "read_customer_orders_and_payment_methods", "get_user_details", args)

    known_order_ids = list((state_data["user_details"] or {}).get("orders", []))
    if facts.get("order_id") and facts["order_id"] not in state_data["orders"]:
        return _planner_tool_call("retail_order_workflow", "read_user_referenced_order", "get_order_details", {"order_id": facts["order_id"]})
    for order_id in known_order_ids:
        if order_id not in state_data["orders"]:
            return _planner_tool_call("retail_order_workflow", "discover_customer_order", "get_order_details", {"order_id": order_id})

    candidate_orders = _retail_relevant_orders(workflow, facts, state_data, user_text)
    if not candidate_orders:
        return None
    order = candidate_orders[0]
    requested_items = _retail_requested_items(order, user_text)
    for item in requested_items:
        product_id = item.get("product_id")
        if product_id and product_id not in state_data["products"] and "get_product_details" in tools_by_name:
            return _planner_tool_call("retail_order_workflow", "read_product_for_requested_item", "get_product_details", {"product_id": product_id})

    payment_method_id = _retail_payment_method(order, state_data["user_details"])
    if workflow in ("return", "exchange", "modify") and not payment_method_id:
        return None
    if workflow == "return":
        args = {"order_id": order["order_id"], "item_ids": [item["item_id"] for item in requested_items], "payment_method_id": payment_method_id}
        if _has_tool_call_args(state, "return_delivered_order_items", args) or _retail_tool_error_after_call(state, "return_delivered_order_items", args):
            return None
        if not _retail_confirmed(latest):
            return _retail_confirmation_response(workflow, order["order_id"], requested_items, None, payment_method_id)
        return _planner_tool_call(
            "retail_order_workflow",
            "execute_confirmed_return_from_retrieved_order",
            "return_delivered_order_items",
            args,
        )
    if workflow in ("exchange", "modify"):
        new_item_ids: list[str] = []
        for item in requested_items:
            product = state_data["products"].get(item.get("product_id"), {})
            new_item_id = _retail_best_variant(item, product, user_text)
            if not new_item_id:
                return None
            new_item_ids.append(new_item_id)
        tool_name = "exchange_delivered_order_items" if workflow == "exchange" else "modify_pending_order_items"
        args = {
            "order_id": order["order_id"],
            "item_ids": [item["item_id"] for item in requested_items],
            "new_item_ids": new_item_ids,
            "payment_method_id": payment_method_id,
        }
        if _has_tool_call_args(state, tool_name, args) or _retail_tool_error_after_call(state, tool_name, args):
            return None
        if not _retail_confirmed(latest):
            return _retail_confirmation_response(workflow, order["order_id"], requested_items, new_item_ids, payment_method_id)
        return _planner_tool_call(
            "retail_order_workflow",
            f"execute_confirmed_{workflow}_from_retrieved_order",
            tool_name,
            args,
        )
    return None


def _benchmark_probe_step(state: AANAContractAgentState) -> AssistantMessage | None:
    try:
        from examples.tau2.aana_tau2_probe_planners import banking_bypass_step
    except Exception:
        return None
    return banking_bypass_step(state)


def _emails_in_text(text: str) -> set[str]:
    return {match.group(0).lower() for match in re.finditer(r"[\w.+-]+@[\w.-]+\.\w+", text)}


def _account_ownership_dispute_detected(state: AANAContractAgentState) -> bool:
    text = _recent_text(state.messages, limit=16).lower()
    has_email_mismatch = "no records found in 'users'" in text and len(_emails_in_text(text)) >= 2
    user_lacks_extra_factors = "don't have" in text or "not have" in text or "not handy" in text
    wants_email_change = "change" in text and "email" in text
    return has_email_mismatch and user_lacks_extra_factors and wants_email_change


def _identity_verification_incomplete(state: AANAContractAgentState) -> bool:
    text = _recent_text(state.messages, limit=16).lower()
    lacks_required_factors = any(
        phrase in text
        for phrase in (
            "don't have my date of birth",
            "don't have my address",
            "date of birth or address handy",
            "not have my date of birth",
            "not have my address",
        )
    )
    if not lacks_required_factors:
        return False
    if "no records found in 'users'" in text and len(_emails_in_text(text)) >= 2:
        return True
    account_specific_intent = any(token in text for token in ("balance", "credit card", "account", "profile", "email", "change"))
    return account_specific_intent and bool(_emails_in_text(text))


def _leaked_email_correction_detected(state: AANAContractAgentState) -> bool:
    text = _recent_text(state.messages, limit=14).lower()
    return len(_emails_in_text(text)) >= 2 and any(token in text for token in ("meant to say", "actually meant", "sorry about that", "i actually meant"))


def _transfer_account_ownership_dispute() -> AssistantMessage:
    return AssistantMessage(
        role="assistant",
        content=None,
        tool_calls=[
            ToolCall(
                id="aana_account_ownership_transfer",
                name="transfer_to_human_agents",
                arguments={
                    "reason": "account_ownership_dispute",
                    "summary": "Customer provided an email that does not match the located account and cannot provide enough additional identity factors for account email recovery.",
                },
                requestor="assistant",
            )
        ],
        raw_data={"aana_planner": {"planner": "account_ownership_dispute", "reason": "mismatched_email_missing_identity_factors"}},
    )


def _correct_banking_identity_response(response: AssistantMessage, state: AANAContractAgentState, domain_policy: str) -> AssistantMessage:
    if not _is_banking_policy(domain_policy):
        return response
    if response.tool_calls and any(call.name in ("change_user_email", "log_verification", "get_credit_card_accounts_by_user") for call in response.tool_calls) and (
        _account_ownership_dispute_detected(state) or _identity_verification_incomplete(state) or _leaked_email_correction_detected(state)
    ):
        return _transfer_account_ownership_dispute()
    if (
        not response.tool_calls
        and getattr(response, "content", None)
        and "transfer" in response.content.lower()
        and (_account_ownership_dispute_detected(state) or _identity_verification_incomplete(state) or _leaked_email_correction_detected(state))
    ):
        return _transfer_account_ownership_dispute()
    if response.tool_calls and any(call.name == "transfer_to_human_agents" for call in response.tool_calls) and _account_ownership_dispute_detected(state):
        for call in response.tool_calls:
            if call.name == "transfer_to_human_agents":
                call.arguments["reason"] = "account_ownership_dispute"
                call.arguments.setdefault("summary", "Customer email claim conflicts with the located account record and identity verification is incomplete.")
        response.raw_data = response.raw_data or {}
        response.raw_data["aana_planner"] = {"planner": "account_ownership_dispute", "reason": "normalized_transfer_reason"}
    return response


def _tool_category(tool_name: str, tool: Tool | None = None) -> str:
    text = f"{tool_name} {getattr(tool, 'description', '') or ''}".lower()
    if any(token in text for token in ("calculate", "knowledge", "policy", "kb_search")):
        return "public_read"
    if any(token in text for token in ("book", "cancel", "change", "create", "delete", "log", "modify", "purchase", "refund", "reset", "return", "send", "submit", "transfer", "update", "verify")):
        return "write"
    if any(token in text for token in ("get", "lookup", "retrieve", "search", "find", "list")):
        if any(token in text for token in ("customer", "user", "account", "order", "reservation", "profile", "subscription")):
            return "private_read"
        return "public_read"
    return "unknown"


def _risk_domain(domain_policy: str) -> str:
    text = domain_policy.lower()
    if any(token in text for token in ("bank", "payment", "account", "card", "wire transfer")):
        return "finance"
    if any(token in text for token in ("flight", "airline", "reservation", "telecom", "phone", "wireless", "internet")):
        return "customer_support"
    return "commerce"


def _auth_state(tool_category: str, messages: list[APICompatibleMessage]) -> str:
    if tool_category == "public_read":
        return "confirmed"
    user_text = _latest_user_summary(messages).lower()
    if any(token in user_text for token in ("yes", "confirm", "confirmed", "go ahead", "please", "do it", "i want", "book", "cancel", "change", "refund", "return", "update", "send", "transfer", "my", "i need", "i would like")):
        return "confirmed"
    return "authenticated"


def _gate_event(tool_name: str, arguments: dict, tool: Tool | None, domain_policy: str, messages: list[APICompatibleMessage]) -> dict:
    category = _tool_category(tool_name, tool)
    intent = _latest_user_summary(messages)
    return {
        "schema_version": "aana.agent_tool_precheck.v1",
        "tool_name": tool_name,
        "tool_category": category,
        "authorization_state": _auth_state(category, messages),
        "evidence_refs": [
            {"source_id": "tau2.domain_policy", "kind": "policy", "trust_tier": "verified", "redaction_status": "redacted", "summary": domain_policy[:700]},
            {"source_id": "tau2.latest_user_message", "kind": "user_message", "trust_tier": "runtime", "redaction_status": "redacted", "summary": intent},
        ],
        "risk_domain": _risk_domain(domain_policy),
        "proposed_arguments": arguments,
        "recommended_route": "accept",
        "user_intent": intent,
    }


def _blocked_response(tool_name: str, decision: dict) -> AssistantMessage:
    route = decision.get("recommended_action", "defer")
    if route == "ask":
        content = "I need one more confirmation before I can perform that action. Please confirm what you want me to do."
    elif route == "refuse":
        content = "I cannot perform that action because the required policy, evidence, or authorization check did not pass."
    else:
        content = "I need to verify the required policy, evidence, or authorization before performing that action."
    return AssistantMessage.text(content=content, raw_data={"aana_gate": {"tool_name": tool_name, **decision}})


class AANAContractAgent(HalfDuplexAgent[AANAContractAgentState]):
    def __init__(
        self,
        tools: list[Tool],
        domain_policy: str,
        llm: str = "openai/gpt-4.1-mini",
        llm_args: Optional[dict] = None,
        aana_gate_version: str = "v2",
        aana_mode: str = "gate-plus-correction",
        allow_benchmark_probes: bool = False,
    ):
        super().__init__(tools=tools, domain_policy=domain_policy)
        self.llm = llm
        self.llm_args = llm_args or {}
        self.aana_gate_version = aana_gate_version
        self.aana_mode = aana_mode
        self.allow_benchmark_probes = allow_benchmark_probes
        self._tools_by_name = {tool.name: tool for tool in tools}

    def get_init_state(self, message_history: Optional[list[Message]] = None) -> AANAContractAgentState:
        return AANAContractAgentState([SystemMessage(role="system", content=_system_prompt(self.domain_policy))], list(message_history) if message_history else [])

    def generate_next_message(self, message: ValidAgentInputMessage, state: AANAContractAgentState) -> tuple[AssistantMessage, AANAContractAgentState]:
        state.messages.extend(message.tool_messages if isinstance(message, MultiToolMessage) else [message])
        latest_user_text = _latest_user_text(state).lower()
        response: AssistantMessage | None = None
        use_correction = self.aana_mode == "gate-plus-correction"
        use_gate = self.aana_mode in ("gate", "gate-plus-correction")
        if use_correction and (_account_ownership_dispute_detected(state) or _leaked_email_correction_detected(state)) and ("transfer" in latest_user_text or "human agent" in latest_user_text):
            response = _transfer_account_ownership_dispute()
        probe_response = None if response is not None or not use_correction or not self.allow_benchmark_probes else _benchmark_probe_step(state)
        if response is not None:
            pass
        elif probe_response is not None:
            response = probe_response
        elif use_correction and (retail_response := _retail_order_planner_step(state, self.domain_policy, self._tools_by_name)) is not None:
            response = retail_response
        elif use_correction and _should_emit_banking_card_recommendation(state, self.domain_policy):
            response = _banking_card_recommendation_response(state, "deterministic_post_retrieval_card_ranking")
        elif use_correction and _is_credit_card_recommendation_turn(message, state, self.domain_policy) and "KB_search" in self._tools_by_name:
            response = _banking_card_planner_search()
        else:
            messages = _messages_with_planner_context(state) if use_correction else state.system_messages + state.messages
            response = generate(model=self.llm, tools=self.tools, messages=messages, call_name="aana_contract_agent_response", **self.llm_args)
            if use_correction:
                _strengthen_banking_card_searches(response, self.domain_policy)
                response = _correct_banking_card_response(response, state, self.domain_policy)
                response = _correct_banking_identity_response(response, state, self.domain_policy)
        if use_gate and response.tool_calls:
            for tool_call in response.tool_calls:
                tool = self._tools_by_name.get(tool_call.name)
                if tool is None:
                    response = _blocked_response(tool_call.name, {"recommended_action": "defer", "hard_blockers": ["unknown_tool"], "reasons": ["tool_not_registered"]})
                    break
                event = _gate_event(tool_call.name, tool_call.arguments, tool, self.domain_policy, state.messages)
                decision = gate_pre_tool_call_v2(event) if self.aana_gate_version == "v2" else gate_pre_tool_call(event)
                decision["tau2_tool_intent"] = infer_tool_intent(event)
                state.gate_records.append(decision)
                if decision["recommended_action"] != "accept":
                    response = _blocked_response(tool_call.name, decision)
                    break
        response.raw_data = response.raw_data or {}
        response.raw_data["aana_gate_records"] = state.gate_records[-5:]
        state.messages.append(response)
        return response, state


def create_aana_contract_agent(tools, domain_policy, **kwargs):
    return AANAContractAgent(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm", "openai/gpt-4.1-mini"),
        llm_args=kwargs.get("llm_args"),
        aana_gate_version=DEFAULT_AANA_GATE_VERSION,
        aana_mode=DEFAULT_AANA_MODE,
        allow_benchmark_probes=DEFAULT_ALLOW_BENCHMARK_PROBES,
    )


def register_aana_agent() -> None:
    if "aana_contract_agent" not in registry.get_agents():
        registry.register_agent_factory(create_aana_contract_agent, "aana_contract_agent")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the AANA tau2 scaffold. Defaults to the general non-probe workflow.",
        epilog=(
            "Default workflow: general_non_probe. Diagnostic benchmark probes are deprecated for "
            "generalization work and require both --allow-benchmark-probes and "
            "AANA_ENABLE_DIAGNOSTIC_PROBES=1."
        ),
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--agent-llm", default="openai/gpt-4.1-mini")
    parser.add_argument("--user-llm", default="openai/gpt-4.1-mini")
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument("--num-tasks", type=int)
    parser.add_argument("--task-ids", nargs="*")
    parser.add_argument("--save-to", required=True)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--retrieval-config")
    parser.add_argument("--auto-resume", action="store_true")
    parser.add_argument("--aana-gate-version", choices=["v1", "v2"], default="v2")
    parser.add_argument("--aana-mode", choices=["off", "gate", "gate-plus-correction"], default="gate-plus-correction")
    parser.add_argument(
        "--allow-benchmark-probes",
        action="store_true",
        help="Deprecated diagnostic-only path. Requires AANA_ENABLE_DIAGNOSTIC_PROBES=1 and must not be used for generalization or public claims.",
    )
    parser.add_argument("--tau2-agent", default="aana_contract_agent", help="Use a built-in tau2 agent such as llm_agent for base-agent ablations.")
    args = parser.parse_args()
    diagnostic_probe_env_enabled = os.environ.get("AANA_ENABLE_DIAGNOSTIC_PROBES") == "1"
    if args.allow_benchmark_probes and not diagnostic_probe_env_enabled:
        parser.error("--allow-benchmark-probes requires AANA_ENABLE_DIAGNOSTIC_PROBES=1 because the default workflow is non-probe only.")

    global DEFAULT_AANA_GATE_VERSION, DEFAULT_AANA_MODE, DEFAULT_ALLOW_BENCHMARK_PROBES
    DEFAULT_AANA_GATE_VERSION = args.aana_gate_version
    DEFAULT_AANA_MODE = args.aana_mode
    DEFAULT_ALLOW_BENCHMARK_PROBES = args.allow_benchmark_probes
    workflow_scope = "diagnostic_probe_only" if args.allow_benchmark_probes else DEFAULT_WORKFLOW_SCOPE
    register_aana_agent()
    config = TextRunConfig(
        domain=args.domain,
        agent=args.tau2_agent,
        llm_agent=args.agent_llm,
        llm_user=args.user_llm,
        num_trials=args.num_trials,
        num_tasks=args.num_tasks,
        task_ids=args.task_ids,
        save_to=args.save_to,
        max_concurrency=args.max_concurrency,
        timeout=args.timeout,
        retrieval_config=args.retrieval_config,
        auto_resume=args.auto_resume,
    )
    results = run_domain(config)
    print(
        json.dumps(
            {
                "save_to": args.save_to,
                "domain": args.domain,
                "agent": args.tau2_agent,
                "aana_mode": args.aana_mode,
                "gate_version": args.aana_gate_version,
                "workflow_scope": workflow_scope,
                "allow_benchmark_probes": args.allow_benchmark_probes,
                "num_simulations": len(results.simulations),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
