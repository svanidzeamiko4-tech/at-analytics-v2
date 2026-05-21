"""
Production readiness checks (Phase 4).

Run at app startup when ``AT_ENV=production`` or ``--production-check`` CLI.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from core.config import get_settings

_DEV_AUTH_SECRET = "at-analytics-dev-secret-change-me"
_DEV_AUTH_SECRET_ALT = "change-me-in-production"


@dataclass
class CheckResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_debug_enabled() -> bool:
    if os.environ.get("AT_DEBUG", "").lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("STREAMLIT_GLOBAL_DEBUG", "").lower() in ("1", "true", "yes"):
        return True
    return False


def check_debug_disabled() -> str | None:
    if _is_debug_enabled():
        return "AT_DEBUG or STREAMLIT_GLOBAL_DEBUG must be false in production"
    return None


def check_auth_secret() -> str | None:
    settings = get_settings()
    secret = settings.auth_secret.strip()
    if secret in (_DEV_AUTH_SECRET, _DEV_AUTH_SECRET_ALT, ""):
        return "AT_AUTH_SECRET must be a strong unique value (not default)"
    if len(secret) < 32:
        return "AT_AUTH_SECRET should be at least 32 characters"
    return None


def check_api_keys() -> list[str]:
    settings = get_settings()
    errors: list[str] = []
    if not (settings.anthropic_api_key or "").strip():
        errors.append("ANTHROPIC_API_KEY is required for AI chat in production")
    if settings.use_postgres and not (settings.database_url or "").strip():
        errors.append("DATABASE_URL is required when USE_POSTGRES=true")
    if not settings.rs_ge_use_mock:
        if not settings.rs_ge_username or not settings.rs_ge_password:
            errors.append("RS_GE_USERNAME and RS_GE_PASSWORD required when RS_GE_USE_MOCK=false")
    return errors


def check_database_connection() -> str | None:
    settings = get_settings()
    if settings.use_postgres:
        try:
            from sqlalchemy import text
            from database.engine import get_engine

            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            return f"PostgreSQL connection failed: {exc}"
    else:
        path = settings.resolved_analytics_sqlite()
        if not path.is_file():
            return f"Analytics SQLite not found: {path}"
    auth_path = settings.auth_db_path
    if not auth_path.is_absolute():
        auth_path = settings.project_root / auth_path
    if not auth_path.is_file():
        return f"Auth SQLite not found: {auth_path} (run app once to init)"
    return None


def run_production_checks(*, strict: bool = True) -> CheckResult:
    """Aggregate checks; ``strict`` raises on errors when used at startup."""
    result = CheckResult(ok=True)

    err = check_debug_disabled()
    if err:
        result.errors.append(err)

    err = check_auth_secret()
    if err:
        result.errors.append(err)

    result.errors.extend(check_api_keys())

    err = check_database_connection()
    if err:
        result.errors.append(err)

    if result.errors:
        result.ok = False

    if strict and not result.ok:
        raise RuntimeError(
            "Production check failed:\n- " + "\n- ".join(result.errors)
        )
    return result


def main() -> int:
    os.environ.setdefault("AT_ENV", "production")
    try:
        run_production_checks(strict=True)
        print("Production checks: OK")
        return 0
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
