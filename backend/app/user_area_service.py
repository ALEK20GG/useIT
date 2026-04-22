"""
User Area Service – Requirements 8.1-8.5

Manages user-specific saved content collections, personal folder organization,
search/filter within saved items, and export functionality (JSON, PDF/text).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

STORAGE_DIR = Path(__file__).parent.parent / "storage" / "user_area"
SAVED_ITEMS_FILE = STORAGE_DIR / "saved_items.json"


class SavedItem:
    """A single saved content item in the user area."""

    def __init__(
        self,
        id: str,
        title: str,
        content: str,
        source: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        folder_path: str = "",
        saved_at: str = "",
    ) -> None:
        self.id = id
        self.title = title
        self.content = content
        self.source = source
        self.notes = notes
        self.tags: list[str] = tags or []
        self.folder_path = folder_path
        self.saved_at = saved_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "notes": self.notes,
            "tags": self.tags,
            "folder_path": self.folder_path,
            "saved_at": self.saved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SavedItem":
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            source=data.get("source", ""),
            notes=data.get("notes", ""),
            tags=data.get("tags", []),
            folder_path=data.get("folder_path", ""),
            saved_at=data.get("saved_at", ""),
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class UserAreaService:
    """CRUD + search + export for user-saved content items."""

    def __init__(self, storage_file: Path = SAVED_ITEMS_FILE) -> None:
        self._storage_file = storage_file
        self._ensure_storage()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_storage(self) -> None:
        """Create storage directory and file if they don't exist."""
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._storage_file.exists():
            self._storage_file.write_text("[]", encoding="utf-8")

    def _load(self) -> list[SavedItem]:
        try:
            raw = json.loads(self._storage_file.read_text(encoding="utf-8"))
            return [SavedItem.from_dict(d) for d in raw]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save(self, items: list[SavedItem]) -> None:
        self._storage_file.write_text(
            json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        title: str,
        content: str,
        source: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        folder_path: str = "",
        content_id: str | None = None,
    ) -> SavedItem:
        """Save a new content item. Returns the created item."""
        items = self._load()
        item = SavedItem(
            id=content_id or str(uuid.uuid4()),
            title=title,
            content=content,
            source=source,
            notes=notes,
            tags=tags or [],
            folder_path=folder_path,
        )
        items.append(item)
        self._save(items)
        return item

    def list_items(
        self,
        search: str = "",
        folder_path: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SavedItem], int]:
        """
        Return (page, total) of saved items.

        Filters:
        - search: case-insensitive substring match on title, content, notes, tags
        - folder_path: exact match on folder_path (empty string = root)
        """
        items = self._load()

        # Filter by folder
        if folder_path is not None:
            items = [i for i in items if i.folder_path == folder_path]

        # Filter by search query
        if search:
            q = search.lower()
            items = [
                i
                for i in items
                if q in i.title.lower()
                or q in i.content.lower()
                or q in i.notes.lower()
                or any(q in tag.lower() for tag in i.tags)
            ]

        # Sort newest first
        items.sort(key=lambda i: i.saved_at, reverse=True)

        total = len(items)
        return items[offset : offset + limit], total

    def get(self, item_id: str) -> SavedItem | None:
        """Return a single item by ID, or None if not found."""
        for item in self._load():
            if item.id == item_id:
                return item
        return None

    def update(
        self,
        item_id: str,
        notes: str | None = None,
        tags: list[str] | None = None,
        folder_path: str | None = None,
        title: str | None = None,
    ) -> SavedItem | None:
        """Update mutable fields of a saved item. Returns updated item or None."""
        items = self._load()
        for item in items:
            if item.id == item_id:
                if notes is not None:
                    item.notes = notes
                if tags is not None:
                    item.tags = tags
                if folder_path is not None:
                    item.folder_path = folder_path
                if title is not None:
                    item.title = title
                self._save(items)
                return item
        return None

    def delete(self, item_id: str) -> bool:
        """Delete an item by ID. Returns True if deleted, False if not found."""
        items = self._load()
        new_items = [i for i in items if i.id != item_id]
        if len(new_items) == len(items):
            return False
        self._save(new_items)
        return True

    # ------------------------------------------------------------------
    # Folder helpers
    # ------------------------------------------------------------------

    def list_folders(self) -> list[str]:
        """Return sorted list of unique folder_path values in use."""
        items = self._load()
        paths = sorted({i.folder_path for i in items if i.folder_path})
        return paths

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_json(self) -> str:
        """Return all saved items serialised as a JSON string."""
        items = self._load()
        return json.dumps(
            [i.to_dict() for i in items],
            ensure_ascii=False,
            indent=2,
        )

    def export_text(self) -> str:
        """
        Return all saved items as a plain-text document.

        Used as a fallback when reportlab is not available.
        """
        items = self._load()
        lines: list[str] = [
            "AREA PERSONALE – CONTENUTI SALVATI",
            f"Esportato il: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}",
            f"Totale elementi: {len(items)}",
            "=" * 60,
            "",
        ]
        for idx, item in enumerate(items, 1):
            lines.append(f"[{idx}] {item.title}")
            if item.folder_path:
                lines.append(f"    Cartella: {item.folder_path}")
            if item.source:
                lines.append(f"    Fonte: {item.source}")
            lines.append(f"    Salvato il: {item.saved_at}")
            if item.tags:
                lines.append(f"    Tag: {', '.join(item.tags)}")
            if item.notes:
                lines.append(f"    Note: {item.notes}")
            lines.append("")
            lines.append("    Contenuto:")
            # Wrap content at ~80 chars
            for para in item.content.split("\n"):
                while len(para) > 76:
                    lines.append(f"    {para[:76]}")
                    para = para[76:]
                lines.append(f"    {para}")
            lines.append("")
            lines.append("-" * 60)
            lines.append("")
        return "\n".join(lines)

    def export_pdf(self) -> bytes | None:
        """
        Return PDF bytes using reportlab, or None if reportlab is unavailable.

        Callers should fall back to export_text() when this returns None.
        """
        try:
            from io import BytesIO

            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                HRFlowable,
            )
            from reportlab.lib import colors

            items = self._load()
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2 * cm,
                leftMargin=2 * cm,
                topMargin=2 * cm,
                bottomMargin=2 * cm,
            )
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Title"],
                fontSize=18,
                spaceAfter=6,
            )
            heading_style = ParagraphStyle(
                "ItemHeading",
                parent=styles["Heading2"],
                fontSize=12,
                spaceAfter=4,
            )
            meta_style = ParagraphStyle(
                "Meta",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.grey,
                spaceAfter=2,
            )
            body_style = ParagraphStyle(
                "Body",
                parent=styles["Normal"],
                fontSize=10,
                spaceAfter=6,
                leading=14,
            )

            story = [
                Paragraph("Area Personale – Contenuti Salvati", title_style),
                Paragraph(
                    f"Esportato il {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')} "
                    f"· {len(items)} element{'o' if len(items) == 1 else 'i'}",
                    meta_style,
                ),
                Spacer(1, 0.4 * cm),
                HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
                Spacer(1, 0.4 * cm),
            ]

            for item in items:
                story.append(Paragraph(_escape_xml(item.title), heading_style))
                meta_parts = []
                if item.folder_path:
                    meta_parts.append(f"📁 {item.folder_path}")
                if item.source:
                    meta_parts.append(f"Fonte: {item.source}")
                meta_parts.append(f"Salvato: {item.saved_at[:10]}")
                if item.tags:
                    meta_parts.append(f"Tag: {', '.join(item.tags)}")
                story.append(Paragraph(" · ".join(meta_parts), meta_style))
                if item.notes:
                    story.append(
                        Paragraph(f"<i>Note: {_escape_xml(item.notes)}</i>", meta_style)
                    )
                story.append(
                    Paragraph(_escape_xml(item.content[:2000]), body_style)
                )
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
                story.append(Spacer(1, 0.3 * cm))

            doc.build(story)
            return buffer.getvalue()

        except ImportError:
            return None


def _escape_xml(text: str) -> str:
    """Escape characters that would break ReportLab XML parsing."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_service: UserAreaService | None = None


def get_user_area_service() -> UserAreaService:
    global _service
    if _service is None:
        _service = UserAreaService()
    return _service
