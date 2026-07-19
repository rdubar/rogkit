"""Tests for the media_files CLI helpers."""

from rogkit_package.bin import media_files


def test_parse_media_file_line_supports_srv_media_root() -> None:
    """Media paths under /srv should parse like /mnt media paths."""
    parsed = media_files.parse_media_file_line(
        "123456 /srv/media/Media/Movies/Some Film (2024)/Some Film.mkv"
    )

    assert parsed is not None
    assert parsed.disk == "media"
    assert parsed.location == "Movies"
    assert parsed.title == "some film (2024)"
    assert parsed.filename == "Some Film.mkv"


def test_group_files_preserves_srv_folder_path() -> None:
    """Folder grouping should not reconstruct /srv paths as /mnt paths."""
    parsed = media_files.parse_media_file_line(
        "123456 /srv/media/Media/Movies/Some Film (2024)/Some Film.mkv"
    )
    assert parsed is not None

    folders = media_files.group_files_into_folders([parsed])

    assert len(folders) == 1
    assert folders[0].folderpath == "/srv/media/Media/Movies/Some Film (2024)"


def test_resolve_media_paths_cli_overrides_config(monkeypatch) -> None:
    """--path should take precedence over configured media folders."""
    monkeypatch.setattr(
        media_files,
        "get_config_value",
        lambda _group, _key: ["/mnt/media1/Media/"],
    )

    assert media_files._resolve_media_paths("/srv/media/Media/") == ["/srv/media/Media/"]


def test_display_duplicates_plain_outputs_no_box_drawing(capsys) -> None:
    """display_duplicates(plain=True) should skip the rich table entirely."""
    duplicates = {"some film": {"media1": 1_000_000_000, "media2": 1_000_000_000}}

    media_files.display_duplicates(duplicates, plain=True)

    out = capsys.readouterr().out
    assert "some film" in out
    assert "media1" in out
    assert "─" not in out
