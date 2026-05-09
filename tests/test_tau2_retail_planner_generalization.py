from pathlib import Path


def test_tau2_retail_planner_does_not_embed_benchmark_entities():
    source = Path("examples/tau2/aana_contract_agent.py").read_text(encoding="utf-8")
    forbidden = (
        "#W2378156",
        "#W6390527",
        "#W6247578",
        "#W9711842",
        "#W4776164",
        "#W6679257",
        "yusuf_rossi",
        "mei_kovacs",
        "credit_card_9513926",
        "paypal_7644869",
        "8384507844",
        "7453605304",
        "7624783998",
        "9523456873",
    )
    assert not [literal for literal in forbidden if literal in source]


def test_tau2_general_scaffold_does_not_embed_probe_entities():
    source = Path("examples/tau2/aana_contract_agent.py").read_text(encoding="utf-8")
    forbidden = (
        "BANKING_BYPASS_CODE",
        "BANKING_BYPASS_QUERY",
        "_banking_bypass_step",
        "9K2X7M4P1N8Q3R5T6A",
        "kenji.tanaka@gmail.com",
        "kenji.tanaka@outlook.com",
        "6680a37184",
    )
    assert not [literal for literal in forbidden if literal in source]


def test_tau2_general_scaffold_keeps_banking_product_constants_in_config():
    source = Path("examples/tau2/aana_contract_agent.py").read_text(encoding="utf-8")
    config = Path("examples/tau2/aana_tau2_adapter_config.json").read_text(encoding="utf-8")
    product_literals = (
        "Gold Rewards Card",
        "Platinum Rewards Card",
        "Silver Rewards Card",
        "Bronze Rewards Card",
        "Rho-Bank+",
    )
    assert not [literal for literal in product_literals if literal in source]
    assert all(literal in config for literal in product_literals)


def test_tau2_default_workflow_is_explicitly_non_probe_only():
    source = Path("examples/tau2/aana_contract_agent.py").read_text(encoding="utf-8")
    assert 'DEFAULT_WORKFLOW_SCOPE = "general_non_probe"' in source
    assert "AANA_ENABLE_DIAGNOSTIC_PROBES" in source
    assert "--allow-benchmark-probes requires AANA_ENABLE_DIAGNOSTIC_PROBES=1" in source
    assert '"workflow_scope": workflow_scope' in source
