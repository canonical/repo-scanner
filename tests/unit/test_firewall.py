"""Tests for the firewall check (repo_scanner.execution.firewall).

The analyzers are fed nft JSON / iptables -S text directly, so neither tool is
invoked.
"""

import json

from repo_scanner.execution.firewall import _analyze_iptables, _analyze_nft

_FORWARD_DROP = {"chain": {"name": "FORWARD", "policy": "drop"}}


def _nft(*objects: dict) -> str:
    return json.dumps({"nftables": list(objects)})


def test_nft_warns_only_on_a_forward_drop_without_a_bridge_accept() -> None:
    accept_policy = {"chain": {"name": "FORWARD", "policy": "accept"}}
    assert _analyze_nft(_nft(accept_policy), "lxdbr0") is None  # not dropping
    bridge_accept = {
        "rule": {
            "chain": "FORWARD",
            "expr": [{"match": {"right": "lxdbr0"}}, {"accept": None}],
        }
    }
    assert _analyze_nft(_nft(_FORWARD_DROP, bridge_accept), "lxdbr0") is None  # allowed
    generic = _analyze_nft(_nft(_FORWARD_DROP), "lxdbr0")  # dropping, no known cause
    assert generic is not None
    assert "add firewall rules allowing forwarding through lxdbr0" in generic


def test_nft_names_the_cause_and_recommends_the_matching_fix() -> None:
    docker = _analyze_nft(
        _nft(_FORWARD_DROP, {"chain": {"name": "DOCKER-USER"}}), "lxdbr0"
    )
    assert docker is not None and "This is likely caused by Docker" in docker
    assert "nft insert rule ip filter DOCKER-USER iifname lxdbr0 accept" in docker
    ufw_chain = {"chain": {"name": "ufw-forward"}}
    ufw = _analyze_nft(_nft(_FORWARD_DROP, ufw_chain), "lxdbr0")
    assert ufw is not None and "ufw route allow in on lxdbr0" in ufw


def test_iptables_warns_only_on_a_forward_drop_without_a_bridge_accept() -> None:
    assert _analyze_iptables("-P FORWARD ACCEPT\n", "lxdbr0") is None  # not dropping
    allowed = "-P FORWARD DROP\n-A FORWARD -o lxdbr0 -j ACCEPT\n"
    assert _analyze_iptables(allowed, "lxdbr0") is None  # bridge explicitly allowed


def test_iptables_names_the_cause_and_recommends_the_matching_fix() -> None:
    rules = "-P FORWARD DROP\n-N DOCKER-USER\n-A FORWARD -j DOCKER-USER\n"
    warning = _analyze_iptables(rules, "lxdbr0")
    assert warning is not None and "This is likely caused by Docker" in warning
    assert "iptables -I DOCKER-USER -i lxdbr0 -j ACCEPT" in warning
