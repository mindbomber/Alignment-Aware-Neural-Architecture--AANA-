"""Compatibility exports for support product-line verifiers.

New code should import support adapters from support_product. This module keeps
the old customer_comms import path stable for existing tests and scripts.
"""

from adapter_runner.verifier_modules.support_product import (  # noqa: F401
    EMAIL_CORRECTION_ROUTES,
    EMAIL_SEND_ROUTE_POLICY,
    INVOICE_BILLING_REPLY_CORRECTION_ROUTES,
    SUPPORT_CORRECTION_ROUTES,
    SUPPORT_REPLY_ROUTE_POLICY,
    TICKET_UPDATE_CORRECTION_ROUTES,
    apply_email_send_route_policy,
    apply_support_reply_route_policy,
    detect_email_send_violations,
    detect_support_reply_violations,
    email_safe_response,
    email_tool_report,
    invoice_billing_reply_repair,
    invoice_billing_reply_tool_report,
    support_customer_name,
    support_safe_response,
    support_tool_report,
    ticket_update_repair,
    ticket_update_tool_report,
)
