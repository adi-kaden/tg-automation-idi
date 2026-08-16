import pytest

from seed import initial_users_from_env


USER_ENV_KEYS = (
    "INITIAL_ADMIN_EMAIL", "INITIAL_ADMIN_PASSWORD",
    "INITIAL_SMM_EMAIL", "INITIAL_SMM_PASSWORD",
    "INITIAL_VIEWER_EMAIL", "INITIAL_VIEWER_PASSWORD",
)


def clear_user_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in USER_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_initial_users_are_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_user_env(monkeypatch)
    assert initial_users_from_env() == []


def test_initial_users_require_complete_credential_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_user_env(monkeypatch)
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "monitor-admin@example.invalid")
    with pytest.raises(ValueError, match="INITIAL_ADMIN_EMAIL/INITIAL_ADMIN_PASSWORD"):
        initial_users_from_env()


def test_initial_users_reject_weak_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_user_env(monkeypatch)
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "monitor-admin@example.invalid")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "too-short")
    with pytest.raises(ValueError, match="INITIAL_ADMIN_PASSWORD"):
        initial_users_from_env()


def test_initial_users_load_only_configured_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_user_env(monkeypatch)
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "monitor-admin@example.invalid")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "long-random-test-value")
    assert initial_users_from_env() == [{
        "email": "monitor-admin@example.invalid",
        "name": "Admin User",
        "password": "long-random-test-value",
        "role": "admin",
    }]
