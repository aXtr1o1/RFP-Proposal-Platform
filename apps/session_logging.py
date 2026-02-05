import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


logger = logging.getLogger("session_logger")


def _get_log_dir() -> Path:
    """
    Resolve a shared logs directory inside the apps package.
    This keeps logs close to the backend code regardless of cwd.
    """
    base_dir = Path(__file__).resolve().parent  # .../apps
    log_dir = base_dir / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.error("Failed to create log directory %s: %s", log_dir, exc)
    return log_dir


def log_openai_usage(
    operation: str,
    *,
    uuid: Optional[str] = None,
    gen_id: Optional[str] = None,
    model: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write a single-session OpenAI usage log as a human-readable .txt file.

    A "session" here maps to a single generation run (word gen, word regen, ppt gen).
    """
    log_dir = _get_log_dir()

    # Build a stable session identifier for the filename
    safe_uuid = uuid or "no_uuid"
    safe_gen = gen_id or "no_gen"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")

    filename = f"{operation}_{safe_uuid}_{safe_gen}_{timestamp}.txt"
    path = log_dir / filename

    lines = [
        f"timestamp_utc: {datetime.utcnow().isoformat()}",
        f"operation: {operation}",
        f"uuid: {uuid or ''}",
        f"gen_id: {gen_id or ''}",
        f"model: {model or ''}",
        f"input_tokens: {input_tokens if input_tokens is not None else ''}",
        f"output_tokens: {output_tokens if output_tokens is not None else ''}",
        f"total_tokens: {total_tokens if total_tokens is not None else ''}",
    ]

    if extra:
        lines.append("extra_context:")
        for key, value in extra.items():
            lines.append(f"  {key}: {value}")

    try:
        with path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        logger.info("Session usage log written: %s", path)
    except Exception as exc:
        logger.exception("Failed to write session usage log to %s: %s", path, exc)


