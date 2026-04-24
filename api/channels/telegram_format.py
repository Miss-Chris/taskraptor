from __future__ import annotations

import html


_PAIRED_TOKENS = (
    ("**", "b"),
    ("__", "u"),
    ("~~", "s"),
    ("||", "tg-spoiler"),
    ("*", "i"),
    ("_", "i"),
)


def markdown_to_telegram_html(text: str) -> str:
    """
    Convert the small Markdown subset produced by assistant replies to Telegram
    HTML. Telegram's Markdown modes are not CommonMark-compatible, so rendering
    HTML is less surprising for model output like ``**bold**``.
    """
    return _render_inline(text)


def _render_inline(text: str) -> str:
    parts: list[str] = []
    index = 0

    while index < len(text):
        if text[index] == "`":
            end = text.find("`", index + 1)
            if end != -1:
                parts.append(f"<code>{html.escape(text[index + 1:end])}</code>")
                index = end + 1
                continue

        matched = False
        for delimiter, tag in _PAIRED_TOKENS:
            if not text.startswith(delimiter, index):
                continue

            end = text.find(delimiter, index + len(delimiter))
            if end == -1:
                continue

            inner = _render_inline(text[index + len(delimiter) : end])
            parts.append(f"<{tag}>{inner}</{tag}>")
            index = end + len(delimiter)
            matched = True
            break

        if matched:
            continue

        parts.append(html.escape(text[index]))
        index += 1

    return "".join(parts)
