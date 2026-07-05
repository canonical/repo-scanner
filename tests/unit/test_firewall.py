"""Tests for the firewall check (repo_scanner.execution.firewall).

The analyzers are fed nft JSON / iptables -S text directly, so neither tool is
invoked.
"""

import json

from repo_scanner.execution.firewall import _analyze_iptables, _analyze_nft

_FORWARD_DROP = {"chain": {"name": "FORWARD", "policy": "drop"}}


def _nft(*objects: dict) -> str:
    return json.dumps({"nftables": list(objects)})


def test_nft_no_warning_when_forward_policy_is_not_drop() -> None:
    assert (
        _analyze_nft(_nft({"chain": {"name": "FORWARD", "policy": "accept"}}), "lxdbr0")
        is None
    )


def test_nft_a_bridge_accept_rule_suppresses_the_warning() -> None:
    accept = {
        "rule": {
            "chain": "FORWARD",
            "expr": [{"match": {"right": "lxdbr0"}}, {"accept": None}],
        }
    }
    assert _analyze_nft(_nft(_FORWARD_DROP, accept), "lxdbr0") is None


def test_nft_docker_cause_recommends_docker_user_rules() -> None:
    warning = _analyze_nft(
        _nft(_FORWARD_DROP, {"chain": {"name": "DOCKER-USER"}}), "lxdbr0"
    )
    assert warning is not None
    assert "This is likely caused by Docker" in warning
    assert "nft insert rule ip filter DOCKER-USER iifname lxdbr0 accept" in warning


def test_nft_ufw_cause_recommends_ufw_rules() -> None:
    warning = _analyze_nft(
        _nft(_FORWARD_DROP, {"chain": {"name": "ufw-forward"}}), "lxdbr0"
    )
    assert warning is not None
    assert "ufw route allow in on lxdbr0" in warning


def test_nft_unknown_cause_gives_generic_advice() -> None:
    warning = _analyze_nft(_nft(_FORWARD_DROP), "lxdbr0")
    assert warning is not None
    assert "add firewall rules allowing forwarding through lxdbr0" in warning


def test_iptables_not_dropping_gives_no_warning() -> None:
    assert _analyze_iptables("-P FORWARD ACCEPT\n", "lxdbr0") is None


def test_iptables_bridge_accept_rule_suppresses_the_warning() -> None:
    rules = "-P FORWARD DROP\n-A FORWARD -o lxdbr0 -j ACCEPT\n"
    assert _analyze_iptables(rules, "lxdbr0") is None


def test_iptables_docker_cause_recommends_iptables_rules() -> None:
    rules = "-P FORWARD DROP\n-N DOCKER-USER\n-A FORWARD -j DOCKER-USER\n"
    warning = _analyze_iptables(rules, "lxdbr0")
    assert warning is not None
    assert "This is likely caused by Docker" in warning
    assert "iptables -I DOCKER-USER -i lxdbr0 -j ACCEPT" in warning
