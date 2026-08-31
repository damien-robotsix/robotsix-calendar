"""Tests for contact operations — CRUD, resolution, serialization, ADR parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotsix_calendar.caldav_client import (
    CalDavClient,
    Contact,
)
from robotsix_calendar.caldav_client.exceptions import (
    NotFoundError,
)
from tests.caldav_client.conftest import _mock_vcard

# ---------------------------------------------------------------------------
# Contacts operations
# ---------------------------------------------------------------------------


class TestListContacts:
    def test_returns_list_of_contacts(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = [_mock_vcard(), _mock_vcard(uid="cnt-2")]

        result = client.list_contacts()

        assert len(result) == 2
        assert isinstance(result[0], Contact)
        assert result[0].uid == "cnt-1"
        assert result[1].uid == "cnt-2"


class TestCreateContact:
    def test_returns_contact_with_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.save_object.return_value = _mock_vcard(uid="new-cnt")

        contact = Contact(full_name="Jane Doe")
        result = client.create_contact(contact)

        assert isinstance(result, Contact)
        assert result.uid == "new-cnt"
        ab.save_object.assert_called_once()


class TestUpdateContact:
    def test_returns_updated_contact(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = [_mock_vcard(uid="cnt-1")]
        ab.save_object.return_value = _mock_vcard(uid="cnt-1", full_name="Jane Updated")

        contact = Contact(full_name="Jane Updated")
        result = client.update_contact("cnt-1", contact)

        assert result.full_name == "Jane Updated"

    def test_raises_not_found_for_unknown_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = []

        with pytest.raises(NotFoundError, match="not found"):
            client.update_contact("unknown", Contact(full_name="X"))


class TestDeleteContact:
    def test_succeeds(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        mock_contact = MagicMock()
        ab.search.return_value = [mock_contact]

        client.delete_contact("cnt-1")  # should not raise

        mock_contact.delete.assert_called_once()

    def test_returns_none_for_unknown_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = []

        result = client.delete_contact("unknown")

        assert result is None


# ---------------------------------------------------------------------------
# Calendar / addressbook resolution
# ---------------------------------------------------------------------------


class TestGetAddressbook:
    def test_no_addressbooks_raises_not_found(self, client: CalDavClient) -> None:
        client._principal.addressbooks.return_value = []

        with pytest.raises(NotFoundError) as exc_info:
            client._get_addressbook()
        assert exc_info.value.code == "not_found"

    def test_named_addressbook_returned(self, client: CalDavClient) -> None:
        ab_a = MagicMock()
        ab_a.name = "personal"
        ab_b = MagicMock()
        ab_b.name = "team"
        client._principal.addressbooks.return_value = [ab_a, ab_b]

        assert client._get_addressbook("team") is ab_b

    def test_named_addressbook_not_found_raises(self, client: CalDavClient) -> None:
        ab_a = MagicMock()
        ab_a.name = "personal"
        client._principal.addressbooks.return_value = [ab_a]

        with pytest.raises(NotFoundError) as exc_info:
            client._get_addressbook("missing")
        assert exc_info.value.code == "not_found"


# ---------------------------------------------------------------------------
# Conversion / serialization helpers
# ---------------------------------------------------------------------------


class TestToContact:
    def test_all_fields_parsed_from_vcard(self) -> None:
        obj = _mock_vcard(
            uid="cnt-1",
            full_name="John Doe",
            email="j@example.com",
            phone="555-1234",
            address="123 Main St",
        )

        contact = CalDavClient._to_contact(obj, addressbook_id="ab")

        assert contact.uid == "cnt-1"
        assert contact.full_name == "John Doe"
        assert contact.email == "j@example.com"
        assert contact.phone == "555-1234"
        assert contact.address == "123 Main St"
        assert contact.addressbook_id == "ab"

    def test_missing_optional_fields_yield_empty(self) -> None:
        obj = _mock_vcard(uid="cnt-9", full_name="Only Name")

        contact = CalDavClient._to_contact(obj, addressbook_id="ab")

        assert contact.uid == "cnt-9"
        assert contact.full_name == "Only Name"
        assert contact.email == ""
        assert contact.phone == ""
        assert contact.address == ""

    def test_no_uid_or_fn_yield_empty(self) -> None:
        obj = MagicMock()
        obj.data = "BEGIN:VCARD\nVERSION:3.0\nEND:VCARD\n"

        contact = CalDavClient._to_contact(obj)

        assert contact.uid == ""
        assert contact.full_name == ""


class TestVcardSerialization:
    def test_includes_optional_fields(self, client: CalDavClient) -> None:
        contact = Contact(
            full_name="Jane",
            email="jane@example.com",
            phone="555-1234",
            address="123 Main St",
        )
        vcard = client._contact_to_vcard(contact)
        assert "EMAIL:jane@example.com" in vcard
        assert "TEL:555-1234" in vcard
        assert "ADR:;;123 Main St;;;" in vcard

    def test_escapes_special_characters(self, client: CalDavClient) -> None:
        contact = Contact(
            full_name="Smith\\, Jane; Jr.\n",
            email="jane+test\\;@example.com",
            phone="555;1234,ext\n9",
            address="123 Main St; Apt 4\\B\nNY, NY",
        )
        vcard = client._contact_to_vcard(contact)
        assert "FN:Smith\\\\\\, Jane\\; Jr.\\n" in vcard
        assert "EMAIL:jane+test\\\\\\;@example.com" in vcard
        assert "TEL:555\\;1234\\,ext\\n9" in vcard
        assert "ADR:;;123 Main St\\; Apt 4\\\\B\\nNY\\, NY;;;" in vcard


# ---------------------------------------------------------------------------
# ADR structured-value parsing (lines 301-323 of _to_contact)
# ---------------------------------------------------------------------------


class TestAdrParsing:
    """Tests for the hand-rolled ADR structured-value parsing in ``_to_contact``.

    Exercises the while-loop that handles ``\\;`` backslash-escaping,
    ``\\n`` newline escaping, multi-component splitting, and empty-component
    filtering.
    """

    @staticmethod
    def _vcard_with_adr(adr_value: str) -> MagicMock:
        """Build a mock vCard object with a specific raw ADR field."""
        obj = MagicMock()
        obj.data = (
            "BEGIN:VCARD\n"
            "VERSION:3.0\n"
            "UID:cnt-1\n"
            "FN:Test Person\n"
            f"ADR:{adr_value}\n"
            "END:VCARD\n"
        )
        return obj

    def test_full_seven_component_address(self) -> None:
        """All 7 vCard ADR components are joined with ``", "``."""
        obj = self._vcard_with_adr(
            "PO Box 123;Suite 100;123 Main St;Springfield;IL;62701;USA"
        )
        contact = CalDavClient._to_contact(obj)
        assert (
            contact.address
            == "PO Box 123, Suite 100, 123 Main St, Springfield, IL, 62701, USA"
        )

    def test_escaped_semicolon_within_component(self) -> None:
        r"""``\\;`` produces a literal ``;`` inside a component, not a separator."""
        obj = self._vcard_with_adr(
            ";;123 Main St\\; Suite 100;Springfield;IL;62701;USA"
        )
        contact = CalDavClient._to_contact(obj)
        assert contact.address == "123 Main St; Suite 100, Springfield, IL, 62701, USA"

    def test_newline_escape_within_component(self) -> None:
        r"""``\\n`` produces a literal newline inside a component."""
        obj = self._vcard_with_adr(";;123 Main St\\nApt 4B;Springfield;IL;62701;USA")
        contact = CalDavClient._to_contact(obj)
        assert contact.address == "123 Main St\nApt 4B, Springfield, IL, 62701, USA"

    def test_empty_leading_components(self) -> None:
        """Empty leading components are filtered out of the joined result."""
        obj = self._vcard_with_adr(";;;Springfield;IL;62701;USA")
        contact = CalDavClient._to_contact(obj)
        assert contact.address == "Springfield, IL, 62701, USA"

    def test_trailing_empty_components(self) -> None:
        """Trailing empty components are filtered out of the joined result."""
        obj = self._vcard_with_adr("123 Main St;Springfield;IL;;;;")
        contact = CalDavClient._to_contact(obj)
        assert contact.address == "123 Main St, Springfield, IL"

    def test_unicode_characters_in_address(self) -> None:
        """Unicode characters are preserved across the parsing loop."""
        obj = self._vcard_with_adr(
            ";;Rue de la République 42;Café;Île-de-France;75001;France"
        )
        contact = CalDavClient._to_contact(obj)
        assert (
            contact.address
            == "Rue de la République 42, Café, Île-de-France, 75001, France"
        )

    def test_no_adr_field(self) -> None:
        """A vCard with no ADR field at all yields an empty address string."""
        obj = MagicMock()
        obj.data = "BEGIN:VCARD\nVERSION:3.0\nUID:cnt-1\nFN:Test Person\nEND:VCARD\n"
        contact = CalDavClient._to_contact(obj)
        assert contact.address == ""

    def test_address_in_sixth_component(self) -> None:
        """Address placed in the 6th component (postal) — the existing pattern."""
        obj = self._vcard_with_adr(";;;;;62701;USA")
        contact = CalDavClient._to_contact(obj)
        assert contact.address == "62701, USA"
