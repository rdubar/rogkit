"""Tests for csvr.py — CSV table viewer."""

import sys
from io import StringIO

import pytest

from rogkit_package.bin.csvr import (
    _detect_delimiter,
    _truncate,
    filter_columns,
    read_csv,
    render_table,
    sort_rows,
)


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------

def test_truncate_short_string():
    assert _truncate("hello", 10) == "hello"

def test_truncate_exact_length():
    assert _truncate("hello", 5) == "hello"

def test_truncate_long_string():
    result = _truncate("hello world", 8)
    assert len(result) == 8
    assert result.endswith("…")

def test_truncate_adds_ellipsis():
    result = _truncate("abcdefgh", 5)
    assert result == "abcd…"


# ---------------------------------------------------------------------------
# _detect_delimiter
# ---------------------------------------------------------------------------

def test_detect_comma():
    assert _detect_delimiter("a,b,c\n1,2,3\n") == ","

def test_detect_tab():
    assert _detect_delimiter("a\tb\tc\n1\t2\t3\n") == "\t"

def test_detect_semicolon():
    assert _detect_delimiter("a;b;c\n1;2;3\n") == ";"

def test_detect_pipe():
    assert _detect_delimiter("a|b|c\n1|2|3\n") == "|"

def test_detect_fallback_single_column():
    # Single column — sniffer may fail; should default to comma
    result = _detect_delimiter("justonecolumn\n")
    assert result == ","


# ---------------------------------------------------------------------------
# read_csv
# ---------------------------------------------------------------------------

def test_read_csv_from_file(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("name,age\nAlice,30\nBob,25\n")
    headers, rows = read_csv(str(f))
    assert headers == ["name", "age"]
    assert rows == [["Alice", "30"], ["Bob", "25"]]

def test_read_csv_no_header(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("Alice,30\nBob,25\n")
    headers, rows = read_csv(str(f), has_header=False)
    assert headers == ["Col1", "Col2"]
    assert len(rows) == 2

def test_read_csv_tab_delimited(tmp_path):
    f = tmp_path / "data.tsv"
    f.write_text("name\tage\nAlice\t30\n")
    headers, rows = read_csv(str(f))
    assert headers == ["name", "age"]
    assert rows[0] == ["Alice", "30"]

def test_read_csv_explicit_delimiter(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("name;age\nAlice;30\n")
    headers, rows = read_csv(str(f), delimiter=";")
    assert headers == ["name", "age"]

def test_read_csv_empty_file(tmp_path):
    f = tmp_path / "empty.csv"
    f.write_text("")
    headers, rows = read_csv(str(f))
    assert headers == []
    assert rows == []

def test_read_csv_from_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", StringIO("x,y\n1,2\n3,4\n"))
    headers, rows = read_csv(None)
    assert headers == ["x", "y"]
    assert len(rows) == 2

def test_read_csv_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_csv("/nonexistent/path/data.csv")


# ---------------------------------------------------------------------------
# filter_columns
# ---------------------------------------------------------------------------

HEADERS = ["name", "age", "city"]
ROWS = [["Alice", "30", "London"], ["Bob", "25", "Paris"]]

def test_filter_keeps_named_columns():
    h, r = filter_columns(HEADERS, ROWS, ["name", "city"])
    assert h == ["name", "city"]
    assert r[0] == ["Alice", "London"]

def test_filter_case_insensitive():
    h, r = filter_columns(HEADERS, ROWS, ["NAME", "AGE"])
    assert h == ["name", "age"]

def test_filter_single_column():
    h, r = filter_columns(HEADERS, ROWS, ["age"])
    assert h == ["age"]
    assert r[0] == ["30"]

def test_filter_nonexistent_raises():
    with pytest.raises(ValueError, match="None of the requested columns"):
        filter_columns(HEADERS, ROWS, ["nonexistent"])

def test_filter_preserves_row_count():
    _, r = filter_columns(HEADERS, ROWS, ["name"])
    assert len(r) == len(ROWS)


# ---------------------------------------------------------------------------
# sort_rows
# ---------------------------------------------------------------------------

def test_sort_alphabetic():
    rows = [["Bob", "25"], ["Alice", "30"]]
    result = sort_rows(["name", "age"], rows, "name")
    assert result[0][0] == "Alice"

def test_sort_numeric():
    rows = [["Alice", "30"], ["Bob", "5"], ["Carol", "15"]]
    result = sort_rows(["name", "age"], rows, "age")
    assert [r[1] for r in result] == ["5", "15", "30"]

def test_sort_descending():
    rows = [["Alice", "30"], ["Bob", "5"], ["Carol", "15"]]
    result = sort_rows(["name", "age"], rows, "age", descending=True)
    assert result[0][1] == "30"

def test_sort_case_insensitive_column():
    rows = [["Bob", "25"], ["Alice", "30"]]
    result = sort_rows(["name", "age"], rows, "NAME")
    assert result[0][0] == "Alice"

def test_sort_missing_column_raises():
    with pytest.raises(ValueError, match="Sort column not found"):
        sort_rows(["name", "age"], ROWS, "nonexistent")


# ---------------------------------------------------------------------------
# render_table (smoke tests — just ensure it doesn't raise)
# ---------------------------------------------------------------------------

def test_render_plain_no_crash(capsys):
    render_table(["a", "b"], [["1", "2"], ["3", "4"]], plain=True)
    out = capsys.readouterr().out
    assert "a" in out
    assert "1" in out

def test_render_empty_no_crash(capsys):
    render_table([], [], plain=True)
    out = capsys.readouterr().out
    assert "empty" in out.lower()

def test_render_with_title(capsys):
    render_table(["x"], [["1"]], title="My Table", plain=True)
    assert "My Table" in capsys.readouterr().out

def test_render_truncates_long_cells(capsys):
    long_val = "x" * 100
    render_table(["col"], [[long_val]], plain=True, truncate=True)
    out = capsys.readouterr().out
    assert "x" * 100 not in out
    assert "…" in out


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

def _run_main(argv: list[str]) -> int:
    old = sys.argv
    sys.argv = ["csv"] + argv
    try:
        from rogkit_package.bin.csvr import main
        return main()
    finally:
        sys.argv = old


def test_main_valid_file(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("name,age\nAlice,30\n")
    assert _run_main([str(f)]) == 0

def test_main_missing_file(tmp_path):
    assert _run_main([str(tmp_path / "nope.csv")]) == 1

def test_main_count(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_text("name,age\nAlice,30\nBob,25\n")
    rc = _run_main([str(f), "--count"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2" in out

def test_main_row_limit(tmp_path, capsys):
    f = tmp_path / "a.csv"
    rows = "name,age\n" + "\n".join(f"Person{i},{i}" for i in range(20))
    f.write_text(rows)
    rc = _run_main([str(f), "-n", "5", "--plain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Person4" in out
    assert "Person5" not in out

def test_main_column_filter(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_text("name,age,city\nAlice,30,London\n")
    rc = _run_main([str(f), "-c", "name,city", "--plain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "name" in out
    assert "city" in out
    assert "age" not in out

def test_main_invalid_column(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("name,age\nAlice,30\n")
    assert _run_main([str(f), "-c", "nonexistent"]) == 1

def test_main_sort(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_text("name,age\nZara,20\nAlice,30\n")
    rc = _run_main([str(f), "-s", "name", "--plain"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.index("Alice") < out.index("Zara")

def test_main_empty_file(tmp_path):
    f = tmp_path / "empty.csv"
    f.write_text("")
    assert _run_main([str(f)]) == 0
