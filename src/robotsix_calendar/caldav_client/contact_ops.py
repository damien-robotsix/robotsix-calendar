"""Contact (CardDAV) CRUD operations for CalDavClient (mixin)."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from ._shared import Contact, _unescape_text, _wrap_caldav_op
from .exceptions import NotFoundError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ._shared import _CalDavClientProtocol

    _MixinBase = _CalDavClientProtocol
else:
    _MixinBase = object


# Backslash-escape sequences recognised inside a structured vCard ADR value.
# Maps the character *following* a backslash to its literal replacement:
#   \\ → literal backslash (does NOT escape the following char)
#   \; → escaped semicolon (literal ";", not a component separator)
#   \, → literal comma
#   \n → newline
_ADR_ESCAPES = {
    "\\": "\\",
    ";": ";",
    ",": ",",
    "n": "\n",
}


def _parse_vcard_adr_field(adr: str) -> list[str]:
    """Split a structured vCard ADR value into its components.

    vCard ADR is a ``;``-separated structured value
    (``PO;ext;street;city;region;postal;country``). Components may contain
    backslash-escaped separators, so splitting must respect the escapes in
    :data:`_ADR_ESCAPES` rather than naively splitting on ``;``.

    Args:
        adr: The raw ADR property value (text after the ``ADR:`` prefix).

    Returns:
        The decoded component strings, in order. Empty components are
        preserved (callers decide whether to drop them).
    """
    components: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(adr):
        ch = adr[i]
        if ch == "\\" and i + 1 < len(adr):
            nxt = adr[i + 1]
            # Known escape → its literal; unknown escape → keep both chars.
            current.append(_ADR_ESCAPES.get(nxt, ch + nxt))
            i += 2
        elif ch == ";":
            components.append("".join(current))
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1
    components.append("".join(current))
    return components


class _ContactOpsMixin(_MixinBase):
    """Mixin providing contact (CardDAV) CRUD methods.

    Mixed into :class:`CalDavClient` alongside the other domain mixins.
    The host-class contract (``_escape_text``, ``_get_addressbook``, ...)
    is supplied under ``TYPE_CHECKING`` by :class:`_CalDavClientProtocol`
    rather than re-declared here.
    """

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_contact(obj: Any, addressbook_id: str = "") -> Contact:
        """Convert a caldav vCard object to our :class:`Contact`.

        ``icalendar`` parses iCalendar only (not vCard), so this reads the raw
        vCard text (``obj.data``) directly instead of the deprecated
        ``vobject_instance``.
        """
        fields: dict[str, str] = {}
        for line in (obj.data or "").splitlines():
            name, sep, value = line.partition(":")
            if not sep:
                continue
            # Property name without parameters (e.g. "TEL;TYPE=cell" -> "TEL").
            key = name.split(";", 1)[0].strip().upper()
            fields.setdefault(key, value)  # first occurrence wins

        address = ""
        adr = fields.get("ADR", "")
        if adr:
            components = _parse_vcard_adr_field(adr)
            address = ", ".join(c for c in components if c)

        return Contact(
            uid=_unescape_text(fields.get("UID", "")),
            full_name=_unescape_text(fields.get("FN", "")),
            email=_unescape_text(fields.get("EMAIL", "")),
            phone=_unescape_text(fields.get("TEL", "")),
            address=address,
            addressbook_id=addressbook_id,
        )

    def _contact_to_vcard(self, contact: Contact) -> str:
        """Build a vCard string from a :class:`Contact`."""
        e = self._escape_text
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{contact.uid or ''}",
            f"FN:{e(contact.full_name)}",
        ]
        if contact.email:
            lines.append(f"EMAIL:{e(contact.email)}")
        if contact.phone:
            lines.append(f"TEL:{e(contact.phone)}")
        if contact.address:
            lines.append(f"ADR:;;{e(contact.address)};;;")
        lines.append("END:VCARD")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Contact CRUD
    # ------------------------------------------------------------------

    @_wrap_caldav_op("list contacts")
    def list_contacts(self, addressbook_id: str = "") -> list[Contact]:
        """Return all contacts.

        If *addressbook_id* is empty, use the default address book.
        """
        logger.debug("list_contacts addressbook_id=%r", addressbook_id)
        ab = self._get_addressbook(addressbook_id)
        results = ab.search()
        return [self._to_contact(r, addressbook_id=ab.name) for r in results]

    @_wrap_caldav_op("create contact")
    def create_contact(self, contact: Contact, addressbook_id: str = "") -> Contact:
        """Create a contact; return the contact with server-assigned uid."""
        logger.debug(
            "create_contact uid=%r addressbook_id=%r full_name=%r",
            contact.uid,
            addressbook_id,
            contact.full_name,
        )
        if not contact.uid:
            contact = Contact(
                uid=str(uuid.uuid4()),
                full_name=contact.full_name,
                email=contact.email,
                phone=contact.phone,
                address=contact.address,
                addressbook_id=contact.addressbook_id,
            )
        ab = self._get_addressbook(addressbook_id)
        vcard = self._contact_to_vcard(contact)
        saved = ab.save_object(vcard)
        return self._to_contact(saved, addressbook_id=ab.name)

    @_wrap_caldav_op("update contact")
    def update_contact(
        self, uid: str, contact: Contact, addressbook_id: str = ""
    ) -> Contact:
        """Update the contact identified by *uid*; return the updated contact.

        Raises:
            NotFoundError: If the UID doesn't exist.
        """
        logger.debug(
            "update_contact uid=%r addressbook_id=%r full_name=%r",
            uid,
            addressbook_id,
            contact.full_name,
        )
        ab = self._get_addressbook(addressbook_id)
        # Fetch to confirm existence — caldav addressbook search by UID
        existing = ab.search(f"UID:{uid}")
        if not existing:
            raise NotFoundError(
                f"Contact with UID {uid!r} not found.",
            )
        # Delete the old vcard and create a new one
        existing[0].delete()
        updated = Contact(
            uid=uid,
            full_name=contact.full_name,
            email=contact.email,
            phone=contact.phone,
            address=contact.address,
            addressbook_id=addressbook_id,
        )
        vcard = self._contact_to_vcard(updated)
        saved = ab.save_object(vcard)
        return self._to_contact(saved, addressbook_id=ab.name)

    @_wrap_caldav_op("delete contact")
    def delete_contact(self, uid: str, addressbook_id: str = "") -> None:
        """Delete the contact identified by *uid*. Idempotent.

        Returns ``None`` when the UID does not exist (already deleted).
        """
        logger.debug("delete_contact uid=%r addressbook_id=%r", uid, addressbook_id)
        ab = self._get_addressbook(addressbook_id)
        existing = ab.search(f"UID:{uid}")
        if not existing:
            return None
        existing[0].delete()
