"""Tests for erpsql.py -- guarded read-only SQL for AI-assisted ERP sessions."""

from __future__ import annotations

import pytest

from rogkit_package.bin import erpsql

ALLOWED = [
    ("count_rows", "SELECT count(*) FROM sale_order WHERE state = 'draft'"),
    ("ids_and_states", "SELECT id, name, state FROM sale_order WHERE id IN (1, 2, 3) ORDER BY id"),
    ("trailing_semicolon", "SELECT id FROM account_invoice;"),
    ("cte", "WITH x AS (SELECT id FROM sale_order) SELECT count(*) FROM x"),
    ("join_partner_ids_only", "SELECT so.id, p.id, p.country_id FROM sale_order so JOIN res_partner p ON p.id = so.partner_id"),
    ("multiplication_not_wildcard", "SELECT price_unit * product_uom_qty AS total FROM sale_order_line"),
    ("column_named_cluster", "SELECT id FROM cluster_table"),
    ("keyword_inside_string", "SELECT id FROM sale_order WHERE name = 'please update email'"),
    ("comment_with_keyword", "SELECT id FROM sale_order -- delete everything"),
    ("information_schema", "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'hr%'"),
    ("create_date_columns", "SELECT id, create_date, write_date FROM sale_order"),
]

BLOCKED = [
    ("select_star", "SELECT * FROM sale_order"),
    ("table_star", "SELECT so.* FROM sale_order so"),
    ("star_after_comma", "SELECT id, * FROM sale_order"),
    ("update", "UPDATE sale_order SET state = 'cancel'"),
    ("delete_cte", "WITH d AS (DELETE FROM sale_order RETURNING id) SELECT count(*) FROM d"),
    ("insert_cte", "WITH d AS (INSERT INTO t VALUES (1) RETURNING id) SELECT id FROM d"),
    ("select_into", "SELECT id INTO newtable FROM sale_order"),
    ("two_statements", "SELECT 1; SELECT 2"),
    ("drop", "DROP TABLE sale_order"),
    ("set_role", "SET ROLE postgres"),
    ("for_update", "SELECT id FROM sale_order FOR UPDATE"),
    ("for_share", "SELECT id FROM sale_order FOR SHARE"),
    ("copy", "COPY sale_order TO '/tmp/x'"),
    ("hr_table", "SELECT id FROM hr_employee"),
    ("hr_payslip", "SELECT count(*) FROM hr_payslip"),
    ("config_parameter", "SELECT key FROM ir_config_parameter"),
    ("quoted_hr_table", 'SELECT count(*) FROM "HR_Employee"'),
    ("password_column", "SELECT password FROM res_users"),
    ("password_crypt", "SELECT password_crypt FROM res_users"),
    ("token_column", "SELECT access_token FROM magento_backend"),
    ("api_key_column", "SELECT api_key FROM some_backend"),
    ("pg_shadow", "SELECT usename FROM pg_shadow"),
    ("email_column", "SELECT email FROM res_partner"),
    ("quoted_email", 'SELECT "email" FROM res_partner'),
    ("street_column", "SELECT p.street FROM res_partner p"),
    ("phone_other_table", "SELECT phone FROM crm_lead"),
    ("partner_name", "SELECT p.name FROM res_partner p"),
    ("partner_display_name", "SELECT display_name FROM res_partner"),
    ("mail_body", "SELECT body FROM mail_message"),
    ("login", "SELECT login FROM res_users"),
    ("read_file_function", "SELECT pg_read_file('/etc/passwd')"),
    ("query_to_xml", "SELECT query_to_xml('select * from hr_employee', true, true, '')"),
    ("nextval", "SELECT nextval('some_seq')"),
    ("dollar_quote", "SELECT $$x$$"),
    ("estring", "SELECT E'\\x41'"),
    ("unterminated_string", "SELECT 'abc FROM sale_order"),
    ("unterminated_comment", "SELECT 1 /* oops"),
    ("starts_with_paren", "(SELECT id FROM sale_order)"),
    ("explain", "EXPLAIN ANALYZE SELECT id FROM sale_order"),
    ("empty", "   "),
]


@pytest.mark.parametrize("name,sql", ALLOWED, ids=[c[0] for c in ALLOWED])
def test_allowed_queries_pass(name: str, sql: str) -> None:
    """Queries that only need IDs, counts, states and dates are allowed."""
    assert erpsql.validate_sql(sql) == []


@pytest.mark.parametrize("name,sql", BLOCKED, ids=[c[0] for c in BLOCKED])
def test_blocked_queries_are_rejected(name: str, sql: str) -> None:
    """Writes, wildcards, red-list and personal-data access are rejected."""
    assert erpsql.validate_sql(sql) != []


def test_extra_config_names_extend_the_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Names listed under [erpsql] in the config add to the built-in deny lists."""
    monkeypatch.setattr(erpsql, "get_config_value", lambda group, key: ["secret_table"] if key == "extra_red_tables" else [])
    assert erpsql.validate_sql("SELECT id FROM secret_table") != []
    assert erpsql.validate_sql("SELECT id FROM other_table") == []


def test_broken_config_does_not_weaken_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """A config read error falls back to the built-in rules."""

    def boom(group: str, key: str):
        raise ValueError("bad config")

    monkeypatch.setattr(erpsql, "get_config_value", boom)
    assert erpsql.validate_sql("SELECT password FROM res_users") != []


def test_limit_wrapper_strips_trailing_semicolon() -> None:
    """The row-cap wrapper must not embed a trailing semicolon inside the subquery."""
    assert erpsql._strip_trailing_semicolon("SELECT 1 ;  ") == "SELECT 1"


def test_check_mode_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    """--check returns 0 for allowed SQL and 2 for blocked SQL, without a connection."""
    assert erpsql.main(["--check", "SELECT count(*) FROM sale_order"]) == 0
    assert erpsql.main(["--check", "SELECT * FROM sale_order"]) == 2
    assert "BLOCKED" in capsys.readouterr().out


def test_live_tunnel_must_use_read_only_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """On live, a tunnel pointing at the writer endpoint is refused."""
    entry = {"system": "erp", "tier": "live", "local_port": 5433, "host_ro": "ro.example", "host_rw": "rw.example",
             "db_user": "u", "db_name": "d", "vaultwarden_item": "x"}
    monkeypatch.setattr(erpsql.tunnel, "_find_entry", lambda system, tier: entry)
    monkeypatch.setattr(erpsql.tunnel, "_listener_pids", lambda port: [123])
    monkeypatch.setattr(erpsql.tunnel, "_tunnel_target", lambda pid: "rw.example")
    monkeypatch.setattr(erpsql.tunnel, "_entry_password", lambda e: "pw")
    conn, error = erpsql._resolve_connection("erp", "live")
    assert conn is None
    assert "read-only" in error


def test_closed_tunnel_is_reported_not_opened(monkeypatch: pytest.MonkeyPatch) -> None:
    """erp_sql never opens a tunnel itself; it tells the user to."""
    entry = {"system": "erp", "tier": "test", "local_port": 5434}
    monkeypatch.setattr(erpsql.tunnel, "_find_entry", lambda system, tier: entry)
    monkeypatch.setattr(erpsql.tunnel, "_listener_pids", lambda port: [])
    conn, error = erpsql._resolve_connection("erp", "test")
    assert conn is None
    assert "tunnel open" in error
