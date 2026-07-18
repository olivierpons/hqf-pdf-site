"""The render server's usage feed.

The render server reports every render it makes to this endpoint, which turns it into a
:class:`~billing.models.UsageRecord` that a month's invoice is totted up from. The
server is the only caller: it authenticates with a shared token in a header, so there is
no session and no CSRF, and the token is the whole of the auth.

A push carries a batch of events. Each names the client the render was for, the server's
own id for it (so a retried push lands once), when it happened, and how many pages it
produced. The client is resolved to an account through its live API key; an event naming
a client no live key knows is refused, and the whole batch with it, so a misconfigured
server is neither billed to the wrong account nor dropped in silence.
"""

import json
import secrets

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from api_keys.models import ApiKey
from billing.models import UsageRecord

USAGE_TOKEN_HEADER = "X-HQF-Usage-Token"
EVENT_ID_MAX = UsageRecord._meta.get_field("event_id").max_length


def _token_ok(request):
    """Return whether the request carries the render server's shared token.

    The comparison is constant-time, so a wrong token leaks nothing through how long it
    takes to reject.
    """
    presented = request.headers.get(USAGE_TOKEN_HEADER, "")
    return secrets.compare_digest(presented, settings.PDF_SERVER_USAGE_TOKEN)


def _field_problem(client_name, event_id, pages, when):
    """Return why the event's fields are invalid, or None when they hold.

    Args:
        client_name: The reported client name.
        event_id: The server's id for the render.
        pages: The page count.
        when: The parsed ``rendered_at``, or None when it did not parse.

    Returns:
        str | None: The first problem found, or None.
    """
    if not isinstance(client_name, str) or not client_name:
        return "client_name must be a non-empty string"
    if not isinstance(event_id, str) or not 0 < len(event_id) <= EVENT_ID_MAX:
        return f"event_id must be a string of 1 to {EVENT_ID_MAX} characters"
    if not isinstance(pages, int) or isinstance(pages, bool) or pages < 0:
        return "pages must be a non-negative integer"
    if when is None:
        return "rendered_at must be an ISO 8601 datetime"
    return None


def _clean_event(raw):
    """Return a validated event dict, or ``(None, reason)`` if it is malformed.

    Args:
        raw: One element of the pushed ``events`` list.

    Returns:
        tuple: ``(event, None)`` with the parsed fields on success, where
        ``rendered_at`` is an aware datetime; ``(None, reason)`` otherwise.
    """
    if not isinstance(raw, dict):
        return None, "each event must be an object"
    missing = {"client_name", "event_id", "rendered_at", "pages"} - raw.keys()
    if missing:
        return None, f"an event is missing {sorted(missing)}"

    raw_when = raw["rendered_at"]
    when = parse_datetime(raw_when) if isinstance(raw_when, str) else None
    reason = _field_problem(raw["client_name"], raw["event_id"], raw["pages"], when)
    if reason:
        return None, reason
    if timezone.is_naive(when):
        when = timezone.make_aware(when)

    return {
        "client_name": raw["client_name"],
        "event_id": raw["event_id"],
        "rendered_at": when,
        "pages": raw["pages"],
    }, None


@csrf_exempt
@require_POST
def ingest_usage(request):
    """Record the renders the server reports, one usage row per event.

    Rejects the batch whole on a bad token (401), an unparseable body or a malformed
    event or unknown client (400). An event whose id is already recorded — a retried
    push, or a duplicate within the same batch — is counted and skipped, so the same
    render is never billed twice.

    Queries: one to map the batch's client names to accounts, one to find which event
    ids are already recorded, then one INSERT per new event, all in a single
    transaction.

    Args:
        request: The POST carrying ``{"events": [...]}`` as JSON.

    Returns:
        JsonResponse: ``{"created": n, "duplicates": m}`` on success.
    """
    if not _token_ok(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "body is not valid JSON"}, status=400)

    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return JsonResponse({"error": "'events' must be a list"}, status=400)

    parsed = []
    for raw in events:
        event, reason = _clean_event(raw)
        if reason:
            return JsonResponse({"error": reason}, status=400)
        parsed.append(event)

    names = {event["client_name"] for event in parsed}
    accounts = {
        key.client_name: key.account_id
        for key in ApiKey.objects.filter(client_name__in=names)
    }
    unknown = sorted(names - set(accounts))
    if unknown:
        return JsonResponse(
            {"error": "unknown client(s)", "clients": unknown}, status=400
        )

    ids = {event["event_id"] for event in parsed}
    seen = set(
        UsageRecord.objects.filter(event_id__in=ids).values_list("event_id", flat=True)
    )

    created = 0
    with transaction.atomic():
        for event in parsed:
            if event["event_id"] in seen:
                continue
            seen.add(event["event_id"])
            UsageRecord.objects.create(
                account_id=accounts[event["client_name"]],
                client_name=event["client_name"],
                event_id=event["event_id"],
                rendered_at=event["rendered_at"],
                pages=event["pages"],
            )
            created += 1

    return JsonResponse({"created": created, "duplicates": len(parsed) - created})
