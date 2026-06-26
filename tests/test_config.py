"""Smoke tests for Stage 0 scaffolding.

These don't touch the network or any real data — they just confirm the package imports and
the reproducibility helper is deterministic, so the skeleton is sound before Stage 1 builds on
it. Real data/backtest tests (where silent bugs hide) arrive with those modules.
"""

import random

import config


def test_package_imports():
    # The pipeline packages should all import cleanly.
    import analysis  # noqa: F401
    import backtest  # noqa: F401
    import data  # noqa: F401
    import features  # noqa: F401
    import paper  # noqa: F401
    import signals  # noqa: F401


def test_seed_everything_is_deterministic():
    config.seed_everything(123)
    a = [random.random() for _ in range(5)]
    config.seed_everything(123)
    b = [random.random() for _ in range(5)]
    assert a == b, "seed_everything must reproduce the same sequence"


def test_default_seed_constant():
    assert config.RANDOM_SEED == 42
    assert config.seed_everything() == 42


def test_edgar_user_agent_has_contact():
    # SEC fair-access requires a descriptive UA; make sure we never send an empty one.
    assert "InsiderSignalResearchEngine" in config.EDGAR_USER_AGENT
    assert config.EDGAR_MAX_REQUESTS_PER_SEC <= 10
