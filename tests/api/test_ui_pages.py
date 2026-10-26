"""Unit tests for :mod:`robotsix_calendar.api._ui_pages` (no TestClient)."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import pytest
from fastapi.responses import RedirectResponse

from robotsix_calendar.api._ui_pages import (
    _UI_NAV,
    _ui_page,
    root_page,
    settings_page,
    ui_calendars_page,
    ui_contacts_page,
    ui_events_page,
    ui_landing_page,
)

_NAV_ENTRY_RE = re.compile(
    r'\{ href: "(?P<href>[^"]+)", label: "(?P<label>[^"]+)", '
    r"active: (?P<active>true|false) \}"
)


class _TitleParser(HTMLParser):
    """Collect the text of every ``<title>`` element."""

    def __init__(self) -> None:
        super().__init__()
        self.titles: list[str] = []
        self._in_title = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],  # noqa: ARG002
    ) -> None:
        if tag == "title":
            self._in_title = True
            self.titles.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.titles[-1] += data


def _nav_entries(html: str) -> list[tuple[str, str, bool]]:
    return [
        (m["href"], m["label"], m["active"] == "true")
        for m in _NAV_ENTRY_RE.finditer(html)
    ]


def _titles(html: str) -> list[str]:
    parser = _TitleParser()
    parser.feed(html)
    return parser.titles


@pytest.mark.parametrize("active_href", [href for href, _ in _UI_NAV])
def test_ui_page_marks_only_matching_nav_item_active(active_href: str) -> None:
    entries = _nav_entries(_ui_page("T", active_href, ""))

    assert [(h, lbl) for h, lbl, _ in entries] == list(_UI_NAV)
    assert [h for h, _, active in entries if active] == [active_href]


def test_ui_page_unknown_active_href_marks_nothing_active() -> None:
    entries = _nav_entries(_ui_page("T", "/nowhere", ""))

    assert len(entries) == len(_UI_NAV)
    assert not any(active for _, _, active in entries)


def test_ui_page_embeds_title() -> None:
    assert _titles(_ui_page("My Page Title", "/ui/events", "")) == ["My Page Title"]


def test_ui_page_inserts_content_unmodified() -> None:
    content = '    <main class="rsu-page"><p id="x">{braces} & "quotes"</p></main>\n'
    html = _ui_page("T", "/ui/events", content)

    assert html.count(content) == 1
    body_start = html.index('<div id="app"></div>')
    shell_script = html.index("mountAppShell")
    assert body_start < html.index(content) < shell_script


def test_root_page_redirects_to_ui_landing() -> None:
    response = root_page()

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui"


@pytest.mark.parametrize(
    ("page", "title", "active_href"),
    [
        (ui_landing_page, "robotsix-calendar", None),
        (ui_calendars_page, "Calendars", "/ui/calendars"),
        (ui_events_page, "Events", "/ui/events"),
        (ui_contacts_page, "Contacts", "/ui/contacts"),
        (settings_page, "Settings", "/settings"),
    ],
)
def test_page_functions_render_title_and_active_nav(
    page: object, title: str, active_href: str | None
) -> None:
    assert callable(page)
    html = page()

    assert _titles(html) == [title]
    active = [h for h, _, is_active in _nav_entries(html) if is_active]
    assert active == ([active_href] if active_href else [])
