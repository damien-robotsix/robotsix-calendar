"""FastAPI HTTP server exposing structured CRUD endpoints.

Provides non-LLM REST endpoints for calendar events, tasks, contacts,
and calendar listing.  The :class:`CalDavClient` instance is injected
via ``app.state.caldav_client`` (set by the entrypoint at startup).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..caldav_client import CalDavClient
from ..caldav_client._shared import CalendarEvent, Contact, Task
from ..caldav_client.exceptions import (
    AuthError,
    CalDAVError,
    CalendarError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

__all__ = ["app"]

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    """Body for creating or updating a calendar event."""

    summary: str
    description: str = ""
    location: str = ""
    dtstart: str
    dtend: str
    calendar_id: str = ""


class EventResponse(BaseModel):
    """Serialized calendar event."""

    uid: str
    summary: str
    description: str
    location: str
    dtstart: str
    dtend: str
    calendar_id: str


class TaskCreate(BaseModel):
    """Body for creating or updating a task."""

    summary: str
    description: str = ""
    dtstart: str = ""
    due: str = ""
    status: str = ""
    calendar_id: str = ""


class TaskResponse(BaseModel):
    """Serialized task."""

    uid: str
    summary: str
    description: str
    dtstart: str
    due: str
    status: str
    calendar_id: str


class ContactCreate(BaseModel):
    """Body for creating or updating a contact."""

    full_name: str
    email: str = ""
    phone: str = ""
    address: str = ""
    addressbook_id: str = ""


class ContactResponse(BaseModel):
    """Serialized contact."""

    uid: str
    full_name: str
    email: str
    phone: str
    address: str
    addressbook_id: str


class CalendarInfo(BaseModel):
    """Serialized calendar entry."""

    name: str


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Calendar Agent API")


# ---------------------------------------------------------------------------
# Dependency — CalDavClient from app.state
# ---------------------------------------------------------------------------


def _get_client(request: Request) -> CalDavClient:
    """Return the shared :class:`CalDavClient` stored on ``app.state``."""
    return request.app.state.caldav_client  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Exception handler — map CalendarError subclasses to HTTP status codes
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[type[CalendarError], int] = {
    NotFoundError: 404,
    AuthError: 401,
    ConflictError: 409,
    RateLimitError: 429,
    CalDAVError: 502,
}


@app.exception_handler(CalendarError)
async def _calendar_error_handler(request: Request, exc: CalendarError) -> JSONResponse:
    status = _STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={"detail": exc.message, "code": exc.code},
    )


# ---------------------------------------------------------------------------
# Helpers — convert dataclass → Pydantic response model
# ---------------------------------------------------------------------------


def _event_to_response(event: CalendarEvent) -> EventResponse:
    return EventResponse(
        uid=event.uid,
        summary=event.summary,
        description=event.description,
        location=event.location,
        dtstart=event.dtstart,
        dtend=event.dtend,
        calendar_id=event.calendar_id,
    )


def _task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        uid=task.uid,
        summary=task.summary,
        description=task.description,
        dtstart=task.dtstart,
        due=task.due,
        status=task.status,
        calendar_id=task.calendar_id,
    )


def _contact_to_response(contact: Contact) -> ContactResponse:
    return ContactResponse(
        uid=contact.uid,
        full_name=contact.full_name,
        email=contact.email,
        phone=contact.phone,
        address=contact.address,
        addressbook_id=contact.addressbook_id,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@app.get("/events", response_model=list[EventResponse])
def list_events(
    start: Annotated[str, Query(description="ISO 8601 start")],
    end: Annotated[str, Query(description="ISO 8601 end")],
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> list[EventResponse]:
    """List events in the given date range."""
    events = client.list_events(start, end, calendar_id)
    return [_event_to_response(e) for e in events]


@app.post("/events", response_model=EventResponse, status_code=201)
def create_event(
    body: EventCreate,
    client: CalDavClient = Depends(_get_client),
) -> EventResponse:
    """Create a new calendar event."""
    event = CalendarEvent(
        summary=body.summary,
        description=body.description,
        location=body.location,
        dtstart=body.dtstart,
        dtend=body.dtend,
        calendar_id=body.calendar_id,
    )
    created = client.create_event(event, calendar_id=body.calendar_id)
    return _event_to_response(created)


@app.put("/events/{uid}", response_model=EventResponse)
def update_event(
    uid: str,
    body: EventCreate,
    client: CalDavClient = Depends(_get_client),
) -> EventResponse:
    """Update an existing calendar event."""
    event = CalendarEvent(
        summary=body.summary,
        description=body.description,
        location=body.location,
        dtstart=body.dtstart,
        dtend=body.dtend,
        calendar_id=body.calendar_id,
    )
    updated = client.update_event(uid, event, calendar_id=body.calendar_id)
    return _event_to_response(updated)


@app.delete("/events/{uid}", status_code=204)
def delete_event(
    uid: str,
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> None:
    """Delete a calendar event (idempotent)."""
    client.delete_event(uid, calendar_id)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@app.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> list[TaskResponse]:
    """List all tasks."""
    tasks = client.list_tasks(calendar_id)
    return [_task_to_response(t) for t in tasks]


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    body: TaskCreate,
    client: CalDavClient = Depends(_get_client),
) -> TaskResponse:
    """Create a new task."""
    task = Task(
        summary=body.summary,
        description=body.description,
        dtstart=body.dtstart,
        due=body.due,
        status=body.status,
        calendar_id=body.calendar_id,
    )
    created = client.create_task(task, calendar_id=body.calendar_id)
    return _task_to_response(created)


@app.put("/tasks/{uid}", response_model=TaskResponse)
def update_task(
    uid: str,
    body: TaskCreate,
    client: CalDavClient = Depends(_get_client),
) -> TaskResponse:
    """Update an existing task."""
    task = Task(
        summary=body.summary,
        description=body.description,
        dtstart=body.dtstart,
        due=body.due,
        status=body.status,
        calendar_id=body.calendar_id,
    )
    updated = client.update_task(uid, task, calendar_id=body.calendar_id)
    return _task_to_response(updated)


@app.delete("/tasks/{uid}", status_code=204)
def delete_task(
    uid: str,
    calendar_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> None:
    """Delete a task (idempotent)."""
    client.delete_task(uid, calendar_id)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


@app.get("/contacts", response_model=list[ContactResponse])
def list_contacts(
    addressbook_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> list[ContactResponse]:
    """List all contacts."""
    contacts = client.list_contacts(addressbook_id)
    return [_contact_to_response(c) for c in contacts]


@app.post("/contacts", response_model=ContactResponse, status_code=201)
def create_contact(
    body: ContactCreate,
    client: CalDavClient = Depends(_get_client),
) -> ContactResponse:
    """Create a new contact."""
    contact = Contact(
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        addressbook_id=body.addressbook_id,
    )
    created = client.create_contact(contact, addressbook_id=body.addressbook_id)
    return _contact_to_response(created)


@app.put("/contacts/{uid}", response_model=ContactResponse)
def update_contact(
    uid: str,
    body: ContactCreate,
    client: CalDavClient = Depends(_get_client),
) -> ContactResponse:
    """Update an existing contact."""
    contact = Contact(
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        addressbook_id=body.addressbook_id,
    )
    updated = client.update_contact(uid, contact, addressbook_id=body.addressbook_id)
    return _contact_to_response(updated)


@app.delete("/contacts/{uid}", status_code=204)
def delete_contact(
    uid: str,
    addressbook_id: Annotated[str, Query()] = "",
    client: CalDavClient = Depends(_get_client),
) -> None:
    """Delete a contact (idempotent)."""
    client.delete_contact(uid, addressbook_id)


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------


@app.get("/calendars", response_model=list[CalendarInfo])
def list_calendars(
    client: CalDavClient = Depends(_get_client),
) -> list[CalendarInfo]:
    """List all calendar names."""
    names = client.list_calendars()
    return [CalendarInfo(name=n) for n in names]
