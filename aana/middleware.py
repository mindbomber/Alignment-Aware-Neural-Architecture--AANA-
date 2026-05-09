"""Dependency-light AANA middleware for common agent/tool runtimes."""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable

from aana.sdk import AANAClient, build_tool_precheck_event, check_tool_call, should_execute_tool, tool_evidence_ref


WRITE_PREFIXES = (
    "add_",
    "append_",
    "approve_",
    "book_",
    "buy_",
    "cancel_",
    "commit_",
    "create_",
    "delete_",
    "deploy_",
    "disable_",
    "enable_",
    "export_",
    "freeze_",
    "grant_",
    "move_",
    "post_",
    "purchase_",
    "refund_",
    "remove_",
    "send_",
    "set_",
    "share_",
    "submit_",
    "transfer_",
    "unfreeze_",
    "update_",
    "write_",
)
PRIVATE_ARGUMENT_KEYS = {
    "account_id",
    "account_key",
    "card_id",
    "client_id",
    "customer_id",
    "employee_id",
    "email",
    "loan_id",
    "patient_id",
    "payment_id",
    "person_id",
    "student_id",
    "transaction_id",
    "user_id",
}
PUBLIC_READ_HINTS = ("public", "score", "weather", "docs", "documentation", "search_web", "web_search", "status")


class AANAToolExecutionBlocked(RuntimeError):
    """Raised when AANA does not allow a proposed tool call."""

    def __init__(self, result: dict[str, Any], event: dict[str, Any]):
        self.result = result
        self.event = event
        super().__init__(f"AANA blocked tool call {event.get('tool_name')!r}: {result.get('recommended_action')}")


def infer_tool_category(tool_name: str, arguments: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str:
    """Infer the AANA tool category when a runtime has not provided one."""

    metadata = metadata or {}
    declared = metadata.get("tool_category")
    if declared in {"public_read", "private_read", "write", "unknown"}:
        return declared

    name = str(tool_name or "").lower()
    args = arguments or {}
    if name.startswith(WRITE_PREFIXES):
        return "write"
    if any(key in args for key in PRIVATE_ARGUMENT_KEYS):
        return "private_read"
    if name.startswith(("get_", "list_", "read_", "search_", "fetch_", "find_")):
        if any(hint in name for hint in PUBLIC_READ_HINTS):
            return "public_read"
        return "private_read"
    if any(hint in name for hint in PUBLIC_READ_HINTS):
        return "public_read"
    return "unknown"


def infer_risk_domain(tool_name: str, metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    declared = metadata.get("risk_domain")
    if declared:
        return str(declared)
    name = str(tool_name or "").lower()
    if any(hint in name for hint in ("deploy", "ci", "kubernetes", "server", "secret", "env", "repo")):
        return "devops"
    if any(hint in name for hint in ("account", "card", "loan", "payment", "refund", "transfer", "invoice")):
        return "finance"
    if any(hint in name for hint in ("employee", "candidate", "payroll", "hr_")):
        return "hr"
    if any(hint in name for hint in ("legal", "contract", "case")):
        return "legal"
    if any(hint in name for hint in ("patient", "medical", "drug", "trial", "pharma")):
        return "pharma"
    if any(hint in name for hint in PUBLIC_READ_HINTS):
        return "public_information"
    return "unknown"


def _metadata_from(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def build_precheck_from_tool_call(
    *,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
    agent_id: str | None = None,
    user_intent: str | None = None,
    recommended_route: str = "accept",
) -> dict[str, Any]:
    """Normalize a framework tool call into `aana.agent_tool_precheck.v1`."""

    metadata = metadata or {}
    args = dict(arguments or {})
    category = infer_tool_category(tool_name, args, metadata)
    auth_state = str(metadata.get("authorization_state") or "none")
    refs = list(evidence_refs or metadata.get("evidence_refs") or [])
    if not refs:
        refs = [
            tool_evidence_ref(
                source_id=f"runtime.tool.{tool_name}",
                kind="policy",
                trust_tier="runtime",
                redaction_status="redacted",
                summary="Runtime provided tool metadata; stronger evidence should be attached for private reads and writes.",
            )
        ]
    return build_tool_precheck_event(
        request_id=request_id or metadata.get("request_id"),
        agent_id=agent_id or metadata.get("agent_id"),
        tool_name=tool_name,
        tool_category=category,
        authorization_state=auth_state,
        evidence_refs=refs,
        risk_domain=infer_risk_domain(tool_name, metadata),
        proposed_arguments=args,
        recommended_route=str(metadata.get("recommended_route") or recommended_route),
        user_intent=user_intent or metadata.get("user_intent"),
        authorization_subject=metadata.get("authorization_subject"),
    )


def gate_tool_call(
    *,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    client: AANAClient | None = None,
    metadata: dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
    agent_id: str | None = None,
    user_intent: str | None = None,
    raise_on_block: bool = True,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run AANA before a framework executes a tool call."""

    event = build_precheck_from_tool_call(
        tool_name=tool_name,
        arguments=arguments,
        metadata=metadata,
        evidence_refs=evidence_refs,
        request_id=request_id,
        agent_id=agent_id,
        user_intent=user_intent,
    )
    result = client.tool_precheck(event) if client else check_tool_call(event)
    gate = {"event": event, "result": result, "allowed": should_execute_tool(result)}
    if on_decision:
        on_decision(gate)
    if raise_on_block and not gate["allowed"]:
        raise AANAToolExecutionBlocked(result, event)
    return gate


def execute_tool_if_allowed(
    tool: Callable[..., Any],
    *,
    tool_name: str | None = None,
    arguments: dict[str, Any] | None = None,
    client: AANAClient | None = None,
    metadata: dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Gate one proposed tool call, execute only if allowed, and return both outputs."""

    name = tool_name or getattr(tool, "__name__", "unknown_tool")
    call_args = dict(arguments or {})
    gate = gate_tool_call(
        tool_name=name,
        arguments=call_args,
        client=client,
        metadata=metadata,
        evidence_refs=evidence_refs,
        on_decision=on_decision,
    )
    return {
        "aana": gate["result"].get("architecture_decision", gate["result"]),
        "gate": gate,
        "tool_result": _call_with_arguments(tool, call_args),
    }


def _call_with_arguments(func: Callable[..., Any], arguments: dict[str, Any]) -> Any:
    try:
        return func(**arguments)
    except TypeError:
        return func(arguments)


def guard_tool_function(
    func: Callable[..., Any],
    *,
    tool_name: str | None = None,
    client: AANAClient | None = None,
    metadata: dict[str, Any] | None = None,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
    raise_on_block: bool = True,
) -> Callable[..., Any]:
    """Wrap a plain sync or async Python tool function with AANA."""

    name = tool_name or getattr(func, "__name__", "unknown_tool")

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            arguments = dict(kwargs) if kwargs else {"args": list(args)}
            gate = gate_tool_call(tool_name=name, arguments=arguments, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            async_wrapper.aana_last_gate = gate
            if not gate["allowed"]:
                return gate
            return await func(*args, **kwargs)

        async_wrapper.aana_last_gate = None
        return async_wrapper

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        arguments = dict(kwargs) if kwargs else {"args": list(args)}
        gate = gate_tool_call(tool_name=name, arguments=arguments, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
        wrapper.aana_last_gate = gate
        if not gate["allowed"]:
            return gate
        return func(*args, **kwargs)

    wrapper.aana_last_gate = None
    return wrapper


def wrap_agent_tool(
    tool: Callable[..., Any],
    *,
    tool_name: str | None = None,
    client: AANAClient | None = None,
    metadata: dict[str, Any] | None = None,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
    raise_on_block: bool = True,
) -> Callable[..., Any]:
    """Plain Python SDK alias for the core agent pattern: propose, gate, execute."""

    return guard_tool_function(
        tool,
        tool_name=tool_name,
        client=client,
        metadata=metadata,
        on_decision=on_decision,
        raise_on_block=raise_on_block,
    )


def langchain_tool_middleware(
    tool: Any,
    *,
    client: AANAClient | None = None,
    metadata: dict[str, Any] | None = None,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
    raise_on_block: bool = True,
) -> Any:
    """Return a LangChain-compatible guarded tool proxy.

    Supports common `invoke`, `ainvoke`, `run`, `arun`, and plain-call tool
    surfaces without importing LangChain.
    """

    name = getattr(tool, "name", None) or getattr(tool, "__name__", "langchain_tool")

    class GuardedLangChainTool:
        def __init__(self, wrapped: Any):
            self.wrapped = wrapped
            self.name = name
            self.description = getattr(wrapped, "description", None)
            self.aana_last_gate = None

        def invoke(self, input: Any, *args: Any, **kwargs: Any) -> Any:
            call_args = input if isinstance(input, dict) else {"input": input}
            self.aana_last_gate = gate_tool_call(tool_name=self.name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            if not self.aana_last_gate["allowed"]:
                return self.aana_last_gate
            return self.wrapped.invoke(input, *args, **kwargs) if hasattr(self.wrapped, "invoke") else _call_with_arguments(self.wrapped, call_args)

        async def ainvoke(self, input: Any, *args: Any, **kwargs: Any) -> Any:
            call_args = input if isinstance(input, dict) else {"input": input}
            self.aana_last_gate = gate_tool_call(tool_name=self.name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            if not self.aana_last_gate["allowed"]:
                return self.aana_last_gate
            if hasattr(self.wrapped, "ainvoke"):
                return await self.wrapped.ainvoke(input, *args, **kwargs)
            return self.invoke(input, *args, **kwargs)

        def run(self, *args: Any, **kwargs: Any) -> Any:
            call_args = dict(kwargs) if kwargs else {"args": list(args)}
            self.aana_last_gate = gate_tool_call(tool_name=self.name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            if not self.aana_last_gate["allowed"]:
                return self.aana_last_gate
            return self.wrapped.run(*args, **kwargs) if hasattr(self.wrapped, "run") else self.wrapped(*args, **kwargs)

        async def arun(self, *args: Any, **kwargs: Any) -> Any:
            call_args = dict(kwargs) if kwargs else {"args": list(args)}
            self.aana_last_gate = gate_tool_call(tool_name=self.name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            if not self.aana_last_gate["allowed"]:
                return self.aana_last_gate
            if hasattr(self.wrapped, "arun"):
                return await self.wrapped.arun(*args, **kwargs)
            return self.run(*args, **kwargs)

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self.run(*args, **kwargs)

    return GuardedLangChainTool(tool)


def openai_agents_tool_middleware(func: Callable[..., Any] | None = None, **options: Any) -> Callable[..., Any]:
    """Decorator for OpenAI Agents SDK tool functions."""

    def decorate(target: Callable[..., Any]) -> Callable[..., Any]:
        return guard_tool_function(
            target,
            tool_name=options.get("tool_name"),
            client=options.get("client"),
            metadata=options.get("metadata"),
            on_decision=options.get("on_decision"),
            raise_on_block=options.get("raise_on_block", True),
        )

    return decorate(func) if func is not None else decorate


def autogen_tool_middleware(func: Callable[..., Any] | None = None, **options: Any) -> Callable[..., Any]:
    """Decorator for AutoGen registered tool functions."""

    return openai_agents_tool_middleware(func, **options)


def crewai_tool_middleware(
    tool: Any,
    *,
    client: AANAClient | None = None,
    metadata: dict[str, Any] | None = None,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
    raise_on_block: bool = True,
) -> Any:
    """Wrap a CrewAI BaseTool-like object or plain function."""

    if callable(tool) and not hasattr(tool, "_run"):
        return guard_tool_function(tool, tool_name=getattr(tool, "__name__", "crewai_tool"), client=client, metadata=metadata, on_decision=on_decision, raise_on_block=raise_on_block)

    name = getattr(tool, "name", None) or tool.__class__.__name__

    class GuardedCrewAITool:
        def __init__(self, wrapped: Any):
            self.wrapped = wrapped
            self.name = name
            self.description = getattr(wrapped, "description", None)
            self.aana_last_gate = None

        def _run(self, *args: Any, **kwargs: Any) -> Any:
            call_args = dict(kwargs) if kwargs else {"args": list(args)}
            self.aana_last_gate = gate_tool_call(tool_name=self.name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            if not self.aana_last_gate["allowed"]:
                return self.aana_last_gate
            return self.wrapped._run(*args, **kwargs)

        async def _arun(self, *args: Any, **kwargs: Any) -> Any:
            call_args = dict(kwargs) if kwargs else {"args": list(args)}
            self.aana_last_gate = gate_tool_call(tool_name=self.name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            if not self.aana_last_gate["allowed"]:
                return self.aana_last_gate
            if hasattr(self.wrapped, "_arun"):
                return await self.wrapped._arun(*args, **kwargs)
            return self._run(*args, **kwargs)

    return GuardedCrewAITool(tool)


def mcp_tool_middleware(
    handler: Callable[..., Any],
    *,
    tool_name: str | None = None,
    client: AANAClient | None = None,
    metadata: dict[str, Any] | None = None,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
    raise_on_block: bool = True,
) -> Callable[..., Any]:
    """Wrap an MCP tool-call handler.

    The wrapper accepts either `(arguments)` or keyword arguments, gates them,
    then delegates to the original handler.
    """

    name = tool_name or getattr(handler, "__name__", "mcp_tool")

    if inspect.iscoroutinefunction(handler):

        @wraps(handler)
        async def async_mcp_wrapper(arguments: dict[str, Any] | None = None, **kwargs: Any) -> Any:
            call_args = dict(arguments or kwargs or {})
            gate = gate_tool_call(tool_name=name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
            async_mcp_wrapper.aana_last_gate = gate
            if not gate["allowed"]:
                return gate
            return await handler(arguments) if arguments is not None and not kwargs else await handler(**kwargs)

        async_mcp_wrapper.aana_last_gate = None
        return async_mcp_wrapper

    @wraps(handler)
    def mcp_wrapper(arguments: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        call_args = dict(arguments or kwargs or {})
        gate = gate_tool_call(tool_name=name, arguments=call_args, client=client, metadata=metadata, raise_on_block=raise_on_block, on_decision=on_decision)
        mcp_wrapper.aana_last_gate = gate
        if not gate["allowed"]:
            return gate
        return handler(arguments) if arguments is not None and not kwargs else handler(**kwargs)

    mcp_wrapper.aana_last_gate = None
    return mcp_wrapper


__all__ = [
    "AANAToolExecutionBlocked",
    "autogen_tool_middleware",
    "build_precheck_from_tool_call",
    "crewai_tool_middleware",
    "gate_tool_call",
    "guard_tool_function",
    "execute_tool_if_allowed",
    "infer_risk_domain",
    "infer_tool_category",
    "langchain_tool_middleware",
    "mcp_tool_middleware",
    "openai_agents_tool_middleware",
    "wrap_agent_tool",
]
