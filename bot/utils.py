import html


def escape_html(text) -> str:
    """Escapes user-supplied text before it is interpolated into a parse_mode='HTML' message."""
    if text is None:
        return ""
    return html.escape(str(text), quote=False)
