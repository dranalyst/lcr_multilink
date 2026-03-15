# services/asterisk_ami.py
import os
import re
from typing import Any, Dict
from asterisk.ami import AMIClient, SimpleAction
from schemas.asterisk_logs import AsteriskCallOrder

ASTERISK_HOST = os.getenv("ASTERISK_HOST", "")
ASTERISK_PORT = int(os.getenv("ASTERISK_PORT", "5038"))
ASTERISK_USERNAME = os.getenv("ASTERISK_USERNAME", "fastapi")
ASTERISK_PASSWORD = os.getenv("ASTERISK_PASSWORD")

COMMPEAK_CONTEXT = os.getenv("COMMPEAK_CONTEXT", "from-internal")
COMMPEAK_PREFIX = os.getenv("COMMPEAK_PREFIX", "9")
COMMPEAK_APP = os.getenv("COMMPEAK_APP", "Playback")
COMMPEAK_APP_DATA = os.getenv("COMMPEAK_APP_DATA", "demo-congrats")


def _format_ami_vars(vars_dict: Dict[str, Any]) -> str:
    parts = []
    for k, v in (vars_dict or {}).items():
        if v is None:
            continue
        v = str(v).strip()
        if v == "":
            continue
        parts.append(f"{k}={v}")
    return "|".join(parts)


def _digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def originate_via_ami(order: AsteriskCallOrder) -> Dict[str, Any]:
    if not ASTERISK_PASSWORD:
        raise RuntimeError("ASTERISK_PASSWORD is not set")

    # provider = (getattr(order, "trunk", None) or "").strip().lower()  # we use trunk as provider-hint
    provider = (
            (getattr(order, "call_provider", None) or "").strip().lower()
            or (getattr(order, "trunk", None) or "").strip().lower()
    )

    src_raw = (getattr(order, "src", "") or "").strip()
    dst_raw = (getattr(order, "dst", "") or "").strip()

    planned_duration = int(getattr(order, "planned_duration", 0) or 0)
    destination_gw = (getattr(order, "destination_gw", "") or "").strip()

    # Common vars (optional; keep them clean — no pipes inside values)
    vars_payload = {
        "__SCHEDULE_ID": str(getattr(order, "schedule_id", 0) or 0),
        "__CALL_SOURCE": "fastapi",
        "__CALL_TYPE": "OUT",
        "__PROVIDER": provider or "",
        "__SRC_RAW": src_raw,
        "__DST_RAW": dst_raw,
        "__PLANNED_DURATION": str(planned_duration),
        "__DESTINATION_GW": destination_gw,
    }

    client = AMIClient(address=ASTERISK_HOST, port=ASTERISK_PORT)
    try:
        client.login(username=ASTERISK_USERNAME, secret=ASTERISK_PASSWORD)

        # ---------------------------------------------------------
        # Provider-specific originate: COMMPEAK
        # ---------------------------------------------------------
        if provider == "commpeak":
            dst_digits = _digits_only(dst_raw)
            src_digits = _digits_only(src_raw)

            if not dst_digits or not src_digits:
                return {
                    "provider": provider,
                    "status": "Error",
                    "message": f"Missing digits: src={src_raw!r} dst={dst_raw!r}",
                }

            # Exactly matches your working CLI:
            # Local/9<dst>*<src>@from-internal
            local_exten = f"{COMMPEAK_PREFIX}{dst_digits}*{src_digits}"
            channel = f"Local/{local_exten}@{COMMPEAK_CONTEXT}"

            action = SimpleAction(
                "Originate",
                Channel=channel,
                Application=COMMPEAK_APP,
                Data=COMMPEAK_APP_DATA,
                CallerID=f"<{src_digits}>",
                Timeout=str(int(getattr(order, "timeout_ms", 30000) or 30000)),
                Variable=_format_ami_vars(vars_payload),
                Async="true",
            )

            future = client.send_action(action)
            ami_response = future.response
            resp_dict = dict(ami_response) if hasattr(ami_response, "items") else {}

            return {
                "provider": provider,
                "context": COMMPEAK_CONTEXT,
                "channel": channel,
                "status": resp_dict.get("Response"),
                "message": resp_dict.get("Message"),
                "actionid": resp_dict.get("ActionID"),
                "raw": resp_dict if resp_dict else str(ami_response),
            }

        # ---------------------------------------------------------
        # Default originate (non-commpeak): Context/Exten
        # ---------------------------------------------------------
        context = getattr(order, "context", None) or "from-internal"
        exten = getattr(order, "exten", None) or (dst_raw or "s")

        channel = f"Local/{exten}@{context}"
        action = SimpleAction(
            "Originate",
            Channel=channel,
            Context=context,
            Exten=exten,
            Priority=str(getattr(order, "priority", 1) or 1),
            CallerID=f"<{src_raw or 'unknown'}>",
            Timeout=str(int(getattr(order, "timeout_ms", 30000) or 30000)),
            Variable=_format_ami_vars(vars_payload),
            Async="true",
        )

        future = client.send_action(action)
        ami_response = future.response
        resp_dict = dict(ami_response) if hasattr(ami_response, "items") else {}

        return {
            "provider": provider or "unknown",
            "context": context,
            "exten": exten,
            "channel": channel,
            "status": resp_dict.get("Response"),
            "message": resp_dict.get("Message"),
            "actionid": resp_dict.get("ActionID"),
            "raw": resp_dict if resp_dict else str(ami_response),
        }

    finally:
        try:
            client.logoff()
        except Exception:
            pass


