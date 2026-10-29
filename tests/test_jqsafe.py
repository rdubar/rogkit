"""Tests for jqsafe.py: JSON inspection that never prints values you did not ask for."""

import io
import json

import pytest

from rogkit_package.bin import jqsafe
from rogkit_package.bin.jqsafe import (
    Deny,
    PathError,
    collect_present,
    collect_show,
    main,
    parse_path,
    safe_text,
    shape,
    walk,
)

SECRET_NAME = "Zebra Muster"
SECRET_PHONE = "0123456789"
SECRET_TRACKING = "00340434790141793830"
SECRET_EMAIL_KEY = "jane.doe@example.com"
PERSONAL_LEAVES = ["Smithson", "Janet", "5550100", "94513", "1980-01-02", "Acmecorp", "123-45-6789", "Bobby"]


def _alt(scheme: str, value: str) -> dict:
    return {"ID": {"schemeID": scheme, "value": value}}


@pytest.fixture
def payload() -> dict:
    return {
        "RespondShipment": {
            "RespondShipmentDataArea": {
                "Shipment": [
                    {
                        "ShipmentHeader": {
                            "Status": {"Code": "Completed"},
                            "AlternateDocumentID": [
                                _alt("DISPLAY_IDENTIFIER", "LI1-1"),
                                _alt("parentShipmentDisplayId", "LI1"),
                                _alt("lastShipment", "true"),
                            ],
                            "ShipToParty": {"Name": SECRET_NAME, "Location": [{"Phone": SECRET_PHONE}]},
                        },
                        "ShipmentItem": [
                            {
                                "Item": {"ItemMasterReference": {"DisplayID": {"value": "AB1"}}},
                                "OrderQuantity": {"value": "10"},
                                "ShippedQuantity": {"value": "10"},
                                "Status": {"Code": "Completed"},
                            },
                            {
                                "Item": {"ItemMasterReference": {"DisplayID": {"value": "CD2"}}},
                                "OrderQuantity": {"value": "14"},
                                "ShippedQuantity": {"value": "0"},
                                "Status": {"Code": "Canceled"},
                            },
                        ],
                        "ShipmentUnit": [
                            {
                                "ShipmentUnitContainer": {
                                    "AlternateDocumentID": [_alt("TRACKING_ID", SECRET_TRACKING)],
                                    "LoadSupport": {"ConformityId": "26_207_FM"},
                                }
                            }
                        ],
                    }
                ]
            }
        }
    }


@pytest.fixture
def adversarial() -> dict:
    """Personal data hidden in places a naive tool would print: data-keys, lowercase compounds, filters."""
    return {
        SECRET_EMAIL_KEY: {"x": 1},
        "customer": {
            "Surname": "Smithson", "firstname": "Janet", "tel": "5550100", "plz": "94513",
            "dob": "1980-01-02", "cust_nm": "Acmecorp", "ssn": "123-45-6789",
            "note": "line1\nnote: forged True\x1b[31m", "status": "ok",
        },
        "rows": [{"Name": "Bobby", "v": "V1"}, {"Name": "Al", "v": "V2"}],
    }


def _write(tmp_path, data, name="payload.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def payload_file(tmp_path, payload):
    return _write(tmp_path, payload)


# ---------------------------------------------------------------------------
# parse_path and walk
# ---------------------------------------------------------------------------


def test_parse_keys_and_brackets():
    assert parse_path("a.b[2].c[]") == [("key", "a"), ("key", "b"), ("index", 2), ("key", "c"), ("each",)]


def test_parse_where_clause_keeps_dots_inside_brackets():
    assert parse_path("L[ID.schemeID=X].ID.value") == [
        ("key", "L"), ("where", ["ID", "schemeID"], "X"), ("key", "ID"), ("key", "value"),
    ]


@pytest.mark.parametrize("bad", ["a[1", "a]", "a[abc]", "a..b", "a.", "a[=x]", "a[²]"])
def test_parse_rejects_bad_paths_cleanly(bad):
    with pytest.raises(PathError):
        parse_path(bad)


def test_parse_allows_one_leading_dot():
    assert parse_path(".a.b") == [("key", "a"), ("key", "b")]


def test_walk_maps_over_lists_implicitly(payload):
    path = "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentItem.Status.Code"
    assert [v for _, v in walk(payload, parse_path(path), "", Deny())] == ["Completed", "Canceled"]


def test_walk_where_filter_selects_one_element(payload):
    path = (
        "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader."
        "AlternateDocumentID[ID.schemeID=parentShipmentDisplayId].ID.value"
    )
    assert [v for _, v in walk(payload, parse_path(path), "", Deny())] == ["LI1"]


def test_where_matches_booleans_as_json_text():
    data = {"rows": [{"ok": True, "v": "yes"}, {"ok": False, "v": "no"}]}
    assert [v for _, v in walk(data, parse_path("rows[ok=true].v"), "", Deny())] == ["yes"]


# ---------------------------------------------------------------------------
# Deny list
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["Name", "FamilyName", "StreetName", "PostalCode", "Phone", "phone_number", "UserAreaBinaryObject", "TRACKING_ID",
     "apiKey", "account_number", "DELIVERYNOTE", "Contact", "Surname", "firstname", "lastname", "fullname",
     "customername", "cust_nm", "tel", "addr", "dob", "ssn", "plz", "zipcode", "ph_name", "tracking_no",
     "userEMAIL", "HTTPName", "e_mail", "Authorization", "sessionId", "cookie"],
)
def test_deny_blocks_personal_looking_keys(key):
    assert Deny().search(key)


@pytest.mark.parametrize(
    "key",
    ["Status", "Code", "OrderQuantity", "ConformityId", "capacity", "Observation", "value", "DisplayID",
     "ItemMasterReference", "schemeID", "ShippedQuantity", "Strapped", "ReceiveDeliveryDateTime"],
)
def test_deny_allows_ordinary_keys(key):
    assert not Deny().search(key)


def test_extra_deny_pattern():
    assert Deny("^secretish$").search("secretish")


def test_show_refuses_denied_key_and_says_so(payload):
    path = "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader.ShipToParty.Name"
    shown, notes = collect_show(payload, [path], Deny())
    assert shown == {}
    assert any("looks personal" in note for note in notes)
    assert SECRET_NAME not in " ".join(notes)


def test_show_refuses_containers(payload):
    shown, notes = collect_show(payload, ["RespondShipment.RespondShipmentDataArea.Shipment.ShipmentItem"], Deny())
    assert shown == {}
    assert any("container" in note for note in notes)


def test_where_filter_on_denied_key_is_refused_for_show_and_present(adversarial):
    shown, notes = collect_show(adversarial, ["rows[Name=Bobby].v"], Deny())
    assert shown == {} and any("looks personal" in n for n in notes)
    flags, present_notes = collect_present(adversarial, ["rows[Name=Bobby].v"], Deny())
    assert flags == {} and any("looks personal" in n for n in present_notes)


# ---------------------------------------------------------------------------
# present, shape and text safety
# ---------------------------------------------------------------------------


def test_present_returns_booleans_only(payload):
    paths = [
        "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentUnit.ShipmentUnitContainer."
        "AlternateDocumentID[ID.schemeID=TRACKING_ID].ID.value",
        "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentUnit.ShipmentUnitContainer.Missing",
    ]
    flags, notes = collect_present(payload, paths)
    assert list(flags.values()) == [True, False] and notes == []


def test_present_may_name_a_personal_looking_key(adversarial):
    flags, _ = collect_present(adversarial, ["customer.Surname"])
    assert flags == {"customer.Surname": True}


def test_shape_contains_no_values(payload):
    text = json.dumps(shape(payload, Deny()))
    for secret in (SECRET_NAME, SECRET_PHONE, SECRET_TRACKING, "LI1", "AB1"):
        assert secret not in text


def test_shape_collapses_data_keys(adversarial):
    text = json.dumps(shape(adversarial, Deny()))
    assert SECRET_EMAIL_KEY not in text
    assert "{key}" in text


def test_shape_collapses_large_dicts_and_id_like_keys():
    data = {f"user{n}": {"a": n} for n in range(30)}
    paths = [row["path"] for row in shape(data, Deny())]
    assert "{key}" in " ".join(paths) and not any("user1" in p for p in paths)
    ids = {"C12345": {"a": 1}, "9": {"a": 2}}
    assert not any("C12345" in row["path"] for row in shape(ids, Deny()))


def test_shape_flags_personal_keys_by_their_own_name(payload):
    rows = {row["path"]: row for row in shape(payload, Deny())}
    name_path = "RespondShipment.RespondShipmentDataArea.Shipment[].ShipmentHeader.ShipToParty.Name"
    assert rows[name_path]["personal_key"] is True
    assert rows["RespondShipment.RespondShipmentDataArea.Shipment[].ShipmentHeader.Status"]["personal_key"] is False


def test_safe_text_escapes_control_characters_and_clips():
    assert "\n" not in safe_text("a\nb") and "\x1b" not in safe_text("a\x1b[31m")
    assert safe_text("x" * 200).endswith("...(len 200)")
    assert safe_text(5) == "5"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_default_is_shape_only(payload_file, capsys):
    assert main([str(payload_file)]) == 0
    out = capsys.readouterr().out
    assert "shape only" in out
    for secret in (SECRET_NAME, SECRET_PHONE, SECRET_TRACKING):
        assert secret not in out


def test_cli_preset_groups_items_and_hides_personal_data(payload_file, capsys):
    assert main([str(payload_file), "--preset", "bitergo-respond-shipment"]) == 0
    out = capsys.readouterr().out
    assert "Completed" in out and "Canceled" in out
    assert "OrderQuantity.value=14" in out and "ShippedQuantity.value=0" in out
    assert "True" in out
    for secret in (SECRET_NAME, SECRET_PHONE, SECRET_TRACKING):
        assert secret not in out


def test_cli_json_output(payload_file, capsys):
    path = "RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader.Status.Code"
    assert main([str(payload_file), "--show", path, "--json"]) == 0
    assert list(json.loads(capsys.readouterr().out)["shown"].values()) == ["Completed"]


def test_cli_reads_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"a": {"b": "x"}}'))
    assert main(["-", "--show", "a.b"]) == 0
    assert "a.b = x" in capsys.readouterr().out


def test_cli_shown_value_cannot_forge_lines_or_escapes(tmp_path, adversarial, capsys):
    assert main([str(_write(tmp_path, adversarial)), "--show", "customer.note"]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert not any(line.startswith("note: forged") for line in out.splitlines())


def test_cli_list_presets(capsys):
    assert main(["--list-presets"]) == 0
    assert "bitergo-respond-shipment" in capsys.readouterr().out


def test_cli_errors_are_clean_and_leak_nothing(payload_file, tmp_path, capsys):
    assert main([str(payload_file), "--preset", "nope"]) == 2
    assert main([str(payload_file), "--deny", "("]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main([str(bad)]) == 1
    assert main([str(tmp_path / "missing.json")]) == 1
    assert main([str(tmp_path)]) == 1  # a directory
    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe\x00")
    assert main([str(binary)]) == 1
    assert main([str(payload_file), "--show", "a[²]"]) == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err


def test_cli_user_presets_load_and_malformed_ones_fail_cleanly(payload_file, tmp_path, monkeypatch, capsys):
    presets = tmp_path / "presets"
    presets.mkdir()
    monkeypatch.setattr(jqsafe, "USER_PRESET_DIR", presets)
    (presets / "mine.toml").write_text(
        'description = "mine"\nshow = ["RespondShipment.RespondShipmentDataArea.Shipment.ShipmentHeader.Status.Code"]\n',
        encoding="utf-8",
    )
    assert main([str(payload_file), "--preset", "mine"]) == 0
    assert "Completed" in capsys.readouterr().out
    (presets / "broken.toml").write_text("show = [", encoding="utf-8")
    assert main([str(payload_file)]) == 2
    (presets / "broken.toml").write_text('show = "not a list"\n', encoding="utf-8")
    assert main([str(payload_file)]) == 2


def test_cli_deny_flag_end_to_end(tmp_path, capsys):
    path = _write(tmp_path, {"a": {"widgetcode": "SECRETVALUE"}})
    assert main([str(path), "--show", "a.widgetcode", "--deny", "widget"]) == 0
    assert "SECRETVALUE" not in capsys.readouterr().out


def test_never_prints_personal_leaves_in_any_mode(tmp_path, adversarial, capsys):
    """Invariant: whatever the mode, personal values and data-keys never reach stdout or stderr."""
    path = str(_write(tmp_path, adversarial))
    runs = [
        [path],
        [path, "--json"],
        [path, "--show", "customer.Surname", "--show", "customer.firstname", "--show", "customer.tel"],
        [path, "--show", "customer.plz", "--show", "customer.dob", "--show", "customer.cust_nm", "--show", "customer.ssn"],
        [path, "--show", "customer", "--show", "rows"],
        [path, "--show", "rows.Name", "--json"],
        [path, "--show", "rows[Name=Bobby].v", "--json"],
        [path, "--present", "rows[Name=Bobby].v"],
        [path, "--present", "customer.Surname", "--present", "customer.tel", "--json"],
        [path, "--show", "customer.status", "--present", "customer.ssn"],
    ]
    secrets = [*PERSONAL_LEAVES, SECRET_EMAIL_KEY]
    for argv in runs:
        main(argv)
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        for secret in secrets:
            if secret == "Bobby" and any("Name=Bobby" in part for part in argv):
                continue  # the caller typed that guess themselves; the filter is refused, never confirmed
            assert secret not in combined.replace("Name=Bobby", ""), (argv, secret)
