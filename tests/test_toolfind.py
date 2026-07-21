"""Tests for toolfind.py - the toolkit's own searchable tool index."""

from __future__ import annotations

from rogkit_package.bin.toolfind import (
    ToolEntry,
    _go_description,
    _parse_aliases,
    _python_docstring,
    _target_for_command,
    build_index,
    main,
    search,
)

FAKE_ALIASES = """\
#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# System Information & Utilities
# ------------------------------------------------------------------------------
alias space='$ROGKIT_GO_BIN/space'
alias note='rogkit_py -m rogkit_package.bin.note'
alias padding='$ROGKIT_PACKAGE/bin/padding.sh'

# ------------------------------------------------------------------------------
# Miscellaneous
# ------------------------------------------------------------------------------
alias filehash='$ROGKIT/rust/target/release/filehash'
alias rogstream='(cd "$ROGKIT" && uv run streamlit run Home.py "$@")'
"""


def test_main_is_callable():
    assert callable(main)


def test_parse_aliases_groups_by_category():
    entries = _parse_aliases(FAKE_ALIASES)
    assert entries == [
        ("space", "$ROGKIT_GO_BIN/space", "System Information & Utilities"),
        ("note", "rogkit_py -m rogkit_package.bin.note", "System Information & Utilities"),
        ("padding", "$ROGKIT_PACKAGE/bin/padding.sh", "System Information & Utilities"),
        ("filehash", "$ROGKIT/rust/target/release/filehash", "Miscellaneous"),
        ("rogstream", '(cd "$ROGKIT" && uv run streamlit run Home.py "$@")', "Miscellaneous"),
    ]


def test_target_for_command_python():
    assert _target_for_command("rogkit_py -m rogkit_package.bin.note") == ("py", "rogkit_package.bin.note")


def test_target_for_command_go():
    assert _target_for_command("$ROGKIT_GO_BIN/space") == ("go", "space")


def test_target_for_command_shell():
    assert _target_for_command("$ROGKIT_PACKAGE/bin/padding.sh") == ("sh", "$ROGKIT_PACKAGE/bin/padding.sh")


def test_target_for_command_rust():
    assert _target_for_command("$ROGKIT/rust/target/release/filehash") == ("rust", "filehash")


def test_target_for_command_streamlit():
    assert _target_for_command('(cd "$ROGKIT" && uv run streamlit run Home.py "$@")') == ("pyfile", "Home.py")


def test_python_docstring_reads_first_line(tmp_path, monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.toolfind.root_dir", str(tmp_path))
    pkg = tmp_path / "rogkit_package" / "bin"
    pkg.mkdir(parents=True)
    (pkg / "widget.py").write_text('"""Does the widget thing.\n\nMore detail.\n"""\n')
    assert _python_docstring("rogkit_package.bin.widget") == "Does the widget thing."


def test_python_docstring_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.toolfind.root_dir", str(tmp_path))
    assert _python_docstring("rogkit_package.bin.nope") == ""


def test_go_description_reads_command_header(tmp_path, monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.toolfind.root_dir", str(tmp_path))
    cmd_dir = tmp_path / "go" / "cmd" / "widget"
    cmd_dir.mkdir(parents=True)
    # Real header comments here are one sentence flowing across lines (see
    # mem/space/sysreboot's main.go), not separate sentences per line.
    (cmd_dir / "main.go").write_text(
        "// Command widget is a small example that does one\n// thing well.\npackage main\n"
    )
    assert _go_description("widget") == "a small example that does one thing well"


def test_build_index_resolves_descriptions(tmp_path, monkeypatch):
    monkeypatch.setattr("rogkit_package.bin.toolfind.root_dir", str(tmp_path))
    (tmp_path / "aliases").write_text(FAKE_ALIASES)
    pkg = tmp_path / "rogkit_package" / "bin"
    pkg.mkdir(parents=True)
    (pkg / "note.py").write_text('"""Quick timestamped note-taking utility."""\n')
    (tmp_path / "Home.py").write_text('"""RogKit Streamlit dashboard."""\n')
    (pkg / "padding.sh").write_text("#!/usr/bin/env bash\n# Remove padding directories.\n")
    cmd_dir = tmp_path / "go" / "cmd" / "space"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "main.go").write_text("// Command space is a fast disk-usage summary.\npackage main\n")
    rust_dir = tmp_path / "rust" / "filehash"
    rust_dir.mkdir(parents=True)
    (rust_dir / "Cargo.toml").write_text('[package]\nname = "filehash"\ndescription = "High-speed file hashing"\n')

    index = build_index()
    by_alias = {e.alias: e for e in index}
    assert by_alias["note"].description == "Quick timestamped note-taking utility."
    assert by_alias["space"].description == "a fast disk-usage summary"
    assert by_alias["padding"].description == "Remove padding directories"
    assert by_alias["filehash"].description == "High-speed file hashing"
    assert by_alias["rogstream"].description == "RogKit Streamlit dashboard."


def test_search_ranks_relevant_entries_first():
    index = [
        ToolEntry("empties", "py:x", "Empty folder and sparse directory finder.", "Files"),
        ToolEntry("chat", "py:y", "ChatGPT CLI client.", "AI"),
    ]
    results = search(index, "empty folders", limit=2)
    assert results[0][0].alias == "empties"


def test_search_promotes_tool_name_in_compound_query():
    index = [
        ToolEntry("space", "go:space", "Disk usage summary.", "System"),
        ToolEntry("system", "py:system", "Enhanced system snapshot.", "System"),
    ]
    results = search(index, "disk space", limit=2)
    assert results[0][0].alias == "space"


def test_search_uses_related_aliases_without_promoting_short_unrelated_aliases():
    index = [
        ToolEntry(
            "clip",
            "py:clipboard",
            "Copy text to the system clipboard.",
            "Text",
            ("clipboard", "clip"),
        ),
        ToolEntry("p", "py:media", "Daemon-backed media search and management utility.", "Media", ("media", "p")),
    ]
    results = search(index, "clipboard", limit=2)
    assert results[0][0].alias == "clip"
    assert results[0][1] >= 98
    assert results[1][0].alias == "p"
    assert results[1][1] < 80
