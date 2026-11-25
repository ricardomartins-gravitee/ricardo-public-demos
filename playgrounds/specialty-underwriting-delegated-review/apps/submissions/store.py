"""Synthetic specialty submissions. One cyber record ships in v1.

A later line of business can be another record with the same fields. This store
does not choose a line, price a risk, or issue coverage.
"""

import threading

LINE_OF_BUSINESS = "CYBER"
IN_REVIEW = "IN_REVIEW"
READY_FOR_QUOTE = "READY_FOR_QUOTE"

_LOCK = threading.Lock()
_WRITES = 0
_RECORDS = {}


def _fixture():
    return {
        "submission_id": "CYB-001",
        "line_of_business": LINE_OF_BUSINESS,
        "status": IN_REVIEW,
        "applicant": "Example Harbor Analytics",
        "attributes": {
            "mfa_coverage_band": "partial",
            "backup_status": "immutable-daily",
        },
        "referral_note": (
            "Synthetic referral: remote access uses partial MFA. "
            "Fixture data for this review demo."
        ),
        # Ownership label for the screen only. Authorization does not read it.
        "sponsor": {"label": "demo metadata", "name": "Example Desk"},
    }


def reset():
    """Restore the seeded record and the write counter. A second call changes nothing."""
    global _WRITES
    with _LOCK:
        _RECORDS.clear()
        _RECORDS[_fixture()["submission_id"]] = _fixture()
        _WRITES = 0
        return snapshot("CYB-001")


def snapshot(submission_id):
    row = _RECORDS.get(submission_id)
    if row is None:
        return None
    body = {key: value for key, value in row.items()}
    body["attributes"] = dict(row["attributes"])
    body["sponsor"] = dict(row["sponsor"])
    body["write_handler_calls"] = _WRITES
    return body


def observation():
    row = snapshot("CYB-001")
    return {
        "submission_id": row["submission_id"],
        "line_of_business": row["line_of_business"],
        "status": row["status"],
        "write_handler_calls": row["write_handler_calls"],
    }


def read_context(submission_id):
    with _LOCK:
        return snapshot(submission_id)


def mark_ready(submission_id):
    """The write handler. Callers that never reach this function leave the counter unchanged."""
    global _WRITES
    with _LOCK:
        row = _RECORDS.get(submission_id)
        if row is None:
            return None
        _WRITES += 1
        if row["status"] == IN_REVIEW:
            row["status"] = READY_FOR_QUOTE
        return snapshot(submission_id)


reset()
