#!/usr/bin/env python3
"""Guarded read-only SQL for ERP databases, for use by AI-assisted sessions.

One sanctioned query path instead of raw psql: SELECT only, no wildcards, no red-list or
personal-data columns, read-only endpoint on live, row cap, timeout, and an audit line per call.

The static checks are guardrails, not a security boundary. The real boundary is the database
role (read-only, granted on masked views only).

The tunnel must already be open (`tunnel open erp live`); this tool never opens one, never
prints a password, and refuses the writer endpoint.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from . import tunnel
from .tomlr import get_config_value

DEFAULT_LIMIT = 50
MAX_LIMIT = 500
DEFAULT_TIMEOUT_S = 15
MAX_TIMEOUT_S = 60
AUDIT_PATH = Path.home() / ".local" / "state" / "rogkit" / "erpsql-audit.log"

# Rule 5: statements and clauses that write, lock, define or run code.
FORBIDDEN_WORDS = frozenset(
    "insert update delete merge drop alter create truncate grant revoke copy call execute set reset into".split()
)
# `FOR UPDATE` is caught above; `FOR SHARE`, `FOR NO KEY UPDATE`, `FOR KEY SHARE` are caught here.
FORBIDDEN_AFTER_FOR = frozenset({"share", "no", "key"})

# Rule 6: function name prefixes that read files, run SQL from strings, or have side effects.
FORBIDDEN_FUNCTION_PREFIXES = (
    "pg_read", "pg_ls", "pg_stat_file", "lo_", "dblink", "set_config", "nextval", "setval",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf", "query_to_xml",
    "table_to_xml", "cursor_to_xml", "schema_to_xml", "database_to_xml", "pg_sleep",
)

# Rule 1: red list. Never, in any tool. Credentials and payroll/employee data.
RED_TABLE_PREFIXES = ("hr_",)
RED_TABLES = frozenset(
    {"ir_config_parameter", "pg_shadow", "pg_authid", "pg_user_mapping", "pg_largeobject"}
)
RED_COLUMN_RE = re.compile(
    r"password|passwd|pwd|token|secret|api_?key|private_?key|credential|salary|wage|payslip"
)

# Rule 2: personal-data columns, blocked wherever they appear.
PII_COLUMNS = frozenset(
    {
        "email", "email_from", "email_to", "email_cc", "email_normalized", "phone", "mobile",
        "fax", "street", "street2", "zip", "city", "vat", "iban", "acc_number", "birthdate",
        "birthday", "ssnid", "sinid", "passport_id",
    }
)

# Rule 3: tables holding people or free text. Referencing one also blocks generic text columns.
PII_TABLES = frozenset(
    {
        "res_partner", "res_partner_bank", "res_partner_address", "res_users", "mail_message",
        "mail_mail", "ir_attachment",
    }
)
PII_TABLE_TEXT_COLUMNS = frozenset(
    {"name", "display_name", "complete_name", "comment", "body", "subject", "login", "website"}
)

_TOKEN_RE = re.compile(
    r"""
    (?P<line_comment>--[^\n]*)
  | (?P<block_comment>/\*.*?\*/)
  | (?P<estring>[eE]'(?:[^'\\]|\\.|'')*')
  | (?P<string>'(?:[^']|'')*')
  | (?P<quoted>"(?:[^"]|"")*")
  | (?P<dollar>\$[A-Za-z_]*\$)
  | (?P<word>[A-Za-z_][A-Za-z0-9_$]*)
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<space>\s+)
  | (?P<punct>::|[^\s])
    """,
    re.VERBOSE | re.DOTALL,
)

RULES_TEXT = """\
Allowed: one SELECT / WITH ... SELECT statement.
1. Red list, never: hr_* tables, ir_config_parameter, password/token/secret/api key/credential/salary columns.
2. Personal-data columns, never: email, phone, mobile, fax, street, zip, city, vat, iban, acc_number, birthdate.
3. If the query touches res_partner, res_users, mail_message, mail_mail, ir_attachment or bank tables:
   also no name, display_name, comment, body, subject, login, website. Use IDs, counts, states, dates.
4. No wildcards (SELECT *, t.*). count(*) is fine.
5. No writes, locks, DDL, SET, COPY, INTO, comments hiding code, dollar quoting or E'' strings.
6. No file, dblink, sequence or query-to-xml functions.
Live is read-only endpoint only. Row cap and timeout apply. Every call is audited.
If a rule blocks something you genuinely need, run it yourself in your own terminal.
"""


class Token(NamedTuple):
    """A SQL token; `text` is lowercased for words and unquoted identifiers."""

    kind: str
    text: str


def tokenise(sql: str) -> list[Token] | None:
    """Split SQL into tokens, dropping comments and whitespace. None if it cannot be parsed."""
    tokens: list[Token] = []
    pos = 0
    while pos < len(sql):
        match = _TOKEN_RE.match(sql, pos)
        if match is None or match.end() == pos:
            return None
        kind = match.lastgroup or "punct"
        text = match.group()
        pos = match.end()
        if kind in {"line_comment", "block_comment", "space"}:
            continue
        if kind == "punct" and (text in {"'", '"'} or sql.startswith("/*", match.start())):
            return None  # unterminated string, quoted identifier or block comment
        if kind == "quoted":
            tokens.append(Token("ident", text[1:-1].replace('""', '"').lower()))
        elif kind == "word":
            tokens.append(Token("word", text.lower()))
        else:
            tokens.append(Token(kind, text))
    return tokens


def _extra(key: str) -> frozenset[str]:
    """Extra lowercase names from [erpsql] in the rogkit config, if any."""
    try:
        value = get_config_value("erpsql", key)
    except Exception:  # config problems must not weaken or break validation
        return frozenset()
    return frozenset(str(v).lower() for v in value) if isinstance(value, list) else frozenset()


def validate_sql(sql: str) -> list[str]:
    """Return a list of violations (empty means the query may run)."""
    if not sql or not sql.strip():
        return ["empty query"]
    tokens = tokenise(sql)
    if tokens is None:
        return ["could not parse the query (unterminated string, quote or comment)"]

    problems: list[str] = []
    if any(t.kind == "dollar" for t in tokens):
        problems.append("dollar quoting is not allowed")
    if any(t.kind == "estring" for t in tokens):
        problems.append("E'' strings are not allowed")

    semicolons = [i for i, t in enumerate(tokens) if t.text == ";"]
    if semicolons and (len(semicolons) > 1 or semicolons[0] != len(tokens) - 1):
        problems.append("only one statement is allowed")
    body = [t for t in tokens if t.text != ";"]
    if not body or body[0].kind != "word" or body[0].text not in {"select", "with"}:
        problems.append("only SELECT or WITH ... SELECT is allowed")

    red_tables = RED_TABLES | _extra("extra_red_tables")
    pii_tables = PII_TABLES | _extra("extra_pii_tables")
    pii_columns = PII_COLUMNS | _extra("extra_pii_columns")

    touches_pii_table = False
    for index, token in enumerate(body):
        previous = body[index - 1] if index else None
        following = body[index + 1] if index + 1 < len(body) else None
        if token.kind == "word":
            if token.text in FORBIDDEN_WORDS:
                problems.append(f"'{token.text}' is not allowed")
            if token.text == "for" and following and following.text in FORBIDDEN_AFTER_FOR:
                problems.append("row locking (FOR UPDATE/SHARE) is not allowed")
            if following and following.text == "(" and token.text.startswith(FORBIDDEN_FUNCTION_PREFIXES):
                problems.append(f"function '{token.text}' is not allowed")
        if token.kind in {"word", "ident"}:
            name = token.text
            if name in red_tables or name.startswith(RED_TABLE_PREFIXES):
                problems.append(f"red list: table '{name}'")
            else:
                if RED_COLUMN_RE.search(name):
                    problems.append(f"red list: '{name}' looks like a credential or salary field")
                if name in pii_columns:
                    problems.append(f"personal data column '{name}'")
            if name in pii_tables:
                touches_pii_table = True
        if token.text == "*":
            after_select = previous is not None and previous.text in {"select", ",", ".", "distinct"}
            in_paren = previous is not None and previous.text == "("
            is_count = in_paren and index >= 2 and body[index - 2].text == "count"
            if after_select or (in_paren and not is_count):
                problems.append("wildcard: list the columns you need (count(*) is fine)")

    if touches_pii_table:
        for token in body:
            if token.kind in {"word", "ident"} and token.text in PII_TABLE_TEXT_COLUMNS:
                problems.append(
                    f"'{token.text}' on a people/free-text table: use IDs, counts, states or dates"
                )
    return sorted(set(problems))


def _audit(record: dict) -> None:
    """Append one JSON line to the local audit log. Never fails the query."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        with AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass


def _strip_trailing_semicolon(sql: str) -> str:
    return sql.strip().rstrip(";").rstrip()


def run_query(conn: dict, sql: str, *, limit: int, timeout_s: int) -> tuple[list[list[str]], bool]:
    """Run a validated query through psql in a read-only session. Returns (rows incl. header, truncated)."""
    wrapped = f"SELECT * FROM ({_strip_trailing_semicolon(sql)}) AS _erpsql LIMIT {limit + 1}"
    env = dict(os.environ)
    env["PGPASSWORD"] = conn["password"]
    env["PGOPTIONS"] = (
        f"-c default_transaction_read_only=on -c statement_timeout={timeout_s * 1000} "
        "-c idle_in_transaction_session_timeout=10000"
    )
    cmd = [
        "psql", "-X", "--csv", "-v", "ON_ERROR_STOP=1",
        "-h", conn["host"], "-p", str(conn["port"]), "-U", conn["user"], "-d", conn["dbname"],
        "-c", wrapped,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout_s + 10)
    if result.returncode != 0:
        lines = [line for line in result.stderr.strip().splitlines() if line.startswith("ERROR")]
        raise RuntimeError(lines[0] if lines else "psql failed")
    rows = list(csv.reader(io.StringIO(result.stdout)))
    truncated = len(rows) - 1 > limit
    return (rows[: limit + 1], truncated)


def _resolve_connection(system: str, tier: str) -> tuple[dict | None, str | None]:
    """Build connection info from the tunnel registry; refuse unsafe states. Returns (conn, error)."""
    entry = tunnel._find_entry(system, tier)
    if entry is None:
        return None, f"No registered entry for {system}/{tier}. Run 'tunnel list'."
    port = entry.get("local_port")
    pids = tunnel._listener_pids(port) if port else []
    if not pids:
        return None, f"No tunnel open on port {port}. Run 'tunnel open {system} {tier}' yourself first."
    if tier.lower() in tunnel._LIVE_TIERS:
        expected = entry.get("host_ro")
        target = tunnel._tunnel_target(pids[0])
        if not expected or target != expected:
            return None, "Refusing: the open live tunnel does not point at the read-only endpoint."
    password = tunnel._entry_password(entry)
    if password is None:
        return None, "Could not fetch the database password (see message above)."
    return (
        {
            "host": "127.0.0.1", "port": port, "user": entry.get("db_user", ""),
            "dbname": entry.get("db_name", ""), "password": password,
        },
        None,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Guarded read-only SQL for ERP databases.")
    parser.add_argument("system", nargs="?", help="registry system, e.g. erp")
    parser.add_argument("tier", nargs="?", help="registry tier, e.g. live or test")
    parser.add_argument("sql", nargs="?", help="the query, or '-' to read it from stdin")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"max rows (default {DEFAULT_LIMIT}, max {MAX_LIMIT})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help=f"seconds (default {DEFAULT_TIMEOUT_S}, max {MAX_TIMEOUT_S})")
    parser.add_argument("--check", action="store_true", help="validate the query only; no connection")
    parser.add_argument("--rules", action="store_true", help="print the rules and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Exit codes: 0 ok, 1 error, 2 blocked by a rule."""
    args = parse_args(argv)
    if args.rules:
        print(RULES_TEXT)
        return 0
    if args.check:
        # `--check` takes just the query: `erp_sql --check "SELECT ..."` or `erp_sql --check - < file`
        sql_arg = args.sql or args.tier or args.system
    else:
        sql_arg = args.sql
    if not sql_arg:
        print("Provide a query (or '-' for stdin). See --rules.", file=sys.stderr)
        return 1
    sql = sys.stdin.read() if sql_arg == "-" else sql_arg

    problems = validate_sql(sql)
    if args.check:
        print("OK" if not problems else "BLOCKED:\n- " + "\n- ".join(problems))
        return 0 if not problems else 2
    if not args.system or not args.tier:
        print("Provide a system and tier, e.g. 'erp live'.", file=sys.stderr)
        return 1
    if problems:
        _audit({"system": args.system, "tier": args.tier, "status": "blocked", "reasons": problems, "sql": sql})
        print("BLOCKED by erp_sql rules:\n- " + "\n- ".join(problems), file=sys.stderr)
        print("Run 'erp_sql --rules' to see them. If you truly need this, run it yourself.", file=sys.stderr)
        return 2

    limit = max(1, min(args.limit, MAX_LIMIT))
    timeout_s = max(1, min(args.timeout, MAX_TIMEOUT_S))
    conn, error = _resolve_connection(args.system, args.tier)
    if conn is None:
        print(error, file=sys.stderr)
        return 1
    try:
        rows, truncated = run_query(conn, sql, limit=limit, timeout_s=timeout_s)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        _audit({"system": args.system, "tier": args.tier, "status": "error", "sql": sql})
        print(f"Query failed: {exc}", file=sys.stderr)
        return 1
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    writer.writerows(rows)
    note = f"{len(rows) - 1} row(s)" + (f", truncated at {limit}" if truncated else "")
    print(f"-- {note}", file=sys.stderr)
    _audit({"system": args.system, "tier": args.tier, "status": "ok", "rows": len(rows) - 1, "sql": sql})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
