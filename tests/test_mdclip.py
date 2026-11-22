"""Tests for mdclip.py - Markdown to rich-text clipboard."""

from __future__ import annotations

from rogkit_package.bin.mdclip import markdown_to_html, prepare_markdown


def test_basic_render():
    html = markdown_to_html("# Title\n\nSome **bold** and a [link](https://x.org).\n")
    assert "<h1>Title</h1>" in html
    assert "<strong>bold</strong>" in html
    assert '<a href="https://x.org">link</a>' in html


def test_bare_url_linked_but_not_in_code():
    html = markdown_to_html("See https://github.com/rdubar/supercomputer\n\n```\nhttps://not.linked\n```\n")
    assert '<a href="https://github.com/rdubar/supercomputer">' in html
    assert '<a href="https://not.linked' not in html


def test_body_drops_title_and_comments():
    src = "# Title\n\n<!-- note to self -->\nText\n"
    out = prepare_markdown(src, body=True)
    assert "Title" not in out and "note to self" not in out and "Text" in out


def test_existing_links_not_doubled():
    html = markdown_to_html("[GitHub](https://github.com)\n")
    assert html.count("<a ") == 1
