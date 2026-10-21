from bot.utils import escape_html


def test_escape_html_escapes_angle_brackets_and_ampersand():
    assert escape_html("5 < 3 & 7 > 1") == "5 &lt; 3 &amp; 7 &gt; 1"


def test_escape_html_leaves_plain_text_unchanged():
    assert escape_html("Fotosintez jarayoni") == "Fotosintez jarayoni"


def test_escape_html_does_not_escape_quotes_by_default():
    # quote=False: this text only ever lands inside Telegram HTML body text, not
    # inside an HTML attribute, so quotes do not need to be escaped.
    assert escape_html('He said "hi"') == 'He said "hi"'


def test_escape_html_handles_none():
    assert escape_html(None) == ""


def test_escape_html_handles_empty_string():
    assert escape_html("") == ""


def test_escape_html_coerces_non_string_input():
    assert escape_html(123) == "123"


def test_escape_html_neutralizes_unclosed_tag_that_would_break_telegram_parsing():
    raw = "mavzu <b>bold"
    escaped = escape_html(raw)
    assert "<b>" not in escaped
    assert escaped == "mavzu &lt;b&gt;bold"
