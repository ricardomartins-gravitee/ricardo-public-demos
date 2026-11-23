"""Deterministic catalog data for the Shared Services API."""

SERVICES = [
    {
        "id": "service-001",
        "name": "Reporting Service",
        "status": "operational",
        "category": "shared-services",
        "owner": "Platform Team",
        "description": "Scheduled and on-demand operational reports.",
    },
    {
        "id": "service-002",
        "name": "Notification Service",
        "status": "operational",
        "category": "shared-services",
        "owner": "Platform Team",
        "description": "Delivery of application notifications.",
    },
    {
        "id": "service-003",
        "name": "Directory Service",
        "status": "degraded",
        "category": "shared-services",
        "owner": "Platform Team",
        "description": "Lookup of shared organizational units.",
    },
    {
        "id": "service-004",
        "name": "Billing Service",
        "status": "operational",
        "category": "shared-services",
        "owner": "Platform Team",
        "description": "Usage records for shared platform services.",
    },
]


# Version 2.0 adds the channel a caller uses. Version 1.0 leaves it off.
CHANNELS = {
    "service-001": "reports",
    "service-002": "notifications",
    "service-003": "directory",
    "service-004": "billing",
}

NOTICES = [
    {
        "id": "notice-001",
        "title": "Directory Service is degraded",
        "status": "active",
        "service": "service-003",
    },
    {
        "id": "notice-002",
        "title": "Reporting Service has a scheduled window",
        "status": "scheduled",
        "service": "service-001",
    },
]


def list_services_envelope():
    return {"count": len(SERVICES), "services": [dict(service) for service in SERVICES]}


def get_service(service_id):
    for service in SERVICES:
        if service["id"] == service_id:
            return dict(service)
    return None


def with_channel(service):
    shown = dict(service)
    shown["channel"] = CHANNELS[service["id"]]
    return shown


def list_services_v2_envelope():
    return {"count": len(SERVICES), "services": [with_channel(service) for service in SERVICES]}


def get_service_v2(service_id):
    service = get_service(service_id)
    return with_channel(service) if service is not None else None


def list_notices_envelope():
    return {"count": len(NOTICES), "notices": [dict(notice) for notice in NOTICES]}


def get_notice(notice_id):
    for notice in NOTICES:
        if notice["id"] == notice_id:
            return dict(notice)
    return None
