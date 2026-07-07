from __future__ import annotations


def redact_logs(log_text: str, secret_values: list[str]) -> str:
    for sv in secret_values:
        if sv and len(sv) >= 4:
            log_text = log_text.replace(sv, "***REDACTED***")
    return log_text
