# app/services/asterisk_ami.py

from typing import Any, Dict, Optional

from asterisk.ami import AMIClient, SimpleAction
from schemas.asterisk_logs import AsteriskCallOrder


# -------------------------------------------------------------------
# Global AMI settings (dev)
# TODO: move these to environment variables / settings
# -------------------------------------------------------------------
# If FastAPI runs on your Mac and Asterisk is in Docker mapped to 5038:
ASTERISK_HOST = "127.0.0.1"
ASTERISK_PORT = 5038

# Must match manager.conf user/secret:
# [fastapi]
# secret = YOUR_REAL_SECRET_HERE
ASTERISK_USERNAME = "fastapi"
ASTERISK_PASSWORD = "+i1u41234567890123456789012345678901234567I="
# -------------------------------------------------------------------


def originate_via_ami(order: AsteriskCallOrder) -> Dict[str, Any]:
    """
    Synchronously originate a call via Asterisk AMI using a typed
    AsteriskCallOrder object. Intended for new endpoints.
    """
    client = AMIClient(address=ASTERISK_HOST, port=ASTERISK_PORT)

    try:
        client.login(username=ASTERISK_USERNAME, secret=ASTERISK_PASSWORD)

        # Build the Asterisk channel to dial
        # If order.trunk is e.g. "PJSIP/mytrunk", channel becomes "PJSIP/mytrunk/<dst>"
        if order.trunk:
            channel = f"{order.trunk}/{order.dst}"
        else:
            # Fallback: dial directly via PJSIP/<dst>
            channel = f"PJSIP/{order.dst}"

        action = SimpleAction(
            "Originate",
            Channel=channel,
            Context=order.context,
            Exten=order.exten,
            Priority=str(order.priority),
            CallerID=order.caller_id or order.src,
            Timeout="30000",   # 30 seconds (milliseconds)
            Variable={
                # Metadata for dialplan / CDR correlation
                "SRC": order.src,
                "DST": order.dst,
                "SCHEDULE_ID": str(order.schedule_id),
                "CALL_SOURCE": "fastapi",
            },
        )

        response = client.send_action(action, timeout=10)

        return {
            "status": response.response.get("Response"),
            "message": response.response.get("Message"),
            "raw": response.response,
        }

    finally:
        try:
            client.logoff()
        except Exception:
            pass


# -------------------------------------------------------------------
# Optional: backward-compatible wrapper (currently NOT used)
# Keep it if some older code still imports originate_call(...)
# -------------------------------------------------------------------
def originate_call(
    host: str,
    port: int,
    username: str,
    secret: str,
    channel: str,
    context: str,
    exten: str,
    priority: int,
    caller_id: str,
    variables: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper for any old code that still calls
    originate_call(...) directly with raw parameters.

    Right now your routers use `originate_via_ami(order)` instead,
    so you *could* safely delete this if nothing else imports it.
    """

    client = AMIClient(address=host, port=port)

    try:
        client.login(username=username, secret=secret)

        vars_str = ",".join(f"{k}={v}" for k, v in (variables or {}).items())

        action = SimpleAction(
            "Originate",
            Channel=channel,      # e.g. SIP/mytrunk/00221xxxxxxx
            Context=context,      # e.g. from-internal
            Exten=exten,          # e.g. 's' or another extension in context
            Priority=str(priority),
            CallerID=caller_id,
            Variable=vars_str,
            Async="true",
        )

        response = client.send_action(action, timeout=10)

        return {
            "status": response.response.get("Response"),
            "message": response.response.get("Message"),
            "raw": response.response,
        }

    finally:
        try:
            client.logoff()
        except Exception:
            pass