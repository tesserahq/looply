"""Architecture guards for transaction ownership, provided by
tessera_sdk.testing.transaction_guards (see docs/managed-transactions.md in
tessera-sdk-py).

Violations are compared with ``transaction_baseline.json``. A violation not in
the baseline fails, and so does a baseline entry that no longer occurs, so
each migration slice shrinks the baseline. Regenerate it after a slice with:

    UPDATE_TRANSACTION_BASELINE=1 ENV=test poetry run pytest tests/architecture

Once a rule's baseline is empty it is fully enforced.
"""

from pathlib import Path

import pytest
from tessera_sdk.testing.transaction_guards import (
    DEFAULT_TRANSACTION_DIRS,
    RULE_NAMES,
    TransactionGuardConfig,
    assert_matches_baseline,
)

CONFIG = TransactionGuardConfig(
    app_root=Path(__file__).parents[2] / "app",
    baseline_path=Path(__file__).with_name("transaction_baseline.json"),
    transaction_dirs=(*DEFAULT_TRANSACTION_DIRS, "ws", "messaging", "integrations"),
    # The SDK auth/onboarding user service is built from db_manager.
    session_modules=("db.py", "services/sdk_user_service.py"),
    repository_base_modules=(),
    # Allowlisted top-level workflows that commit early around external I/O:
    # (path relative to app/, function name) -> reason.
    early_commit_allowlist={},
)


@pytest.mark.parametrize("rule", RULE_NAMES)
def test_transaction_rule_matches_baseline(rule):
    assert_matches_baseline(CONFIG, rule)
