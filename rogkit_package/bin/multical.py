#!/usr/bin/env python3
import argparse
import datetime
from convertdate import (
    julian,
    hebrew,
    islamic,
    persian,
    bahai,
    indian_civil,
    mayan,
)

try:  # optional rich formatting
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False

# try:
#     from convertdate import islamic_umalqura
# except ImportError:
#     islamic_umalqura = None

def main():
    parser = argparse.ArgumentParser(
        description="Show a date in all calendars supported by convertdate."
    )
    parser.add_argument(
        "date",
        nargs="?",
        help="Date in YYYY-MM-DD format (defaults to today)."
    )
    args = parser.parse_args()

    # Determine input date
    if args.date:
        try:
            year, month, day = map(int, args.date.split("-"))
            g_date = datetime.date(year, month, day)
        except Exception:
            print("Invalid date format. Use YYYY-MM-DD.")
            return
    else:
        g_date = datetime.date.today()

    y, m, d = g_date.year, g_date.month, g_date.day

    header = f"Input Gregorian date: {y:04d}-{m:02d}-{d:02d}"
    entries = []

    entries.append(("Gregorian", f"{y}-{m}-{d}"))

    jy, jm, jd = julian.from_gregorian(y, m, d)
    entries.append(("Julian", f"{jy}-{jm}-{jd}"))

    hy, hm, hd = hebrew.from_gregorian(y, m, d)
    entries.append(("Hebrew", f"{hy}-{hm}-{hd}"))

    iy, im, id_ = islamic.from_gregorian(y, m, d)
    entries.append(("Islamic (Tabular)", f"{iy}-{im}-{id_}"))

    py, pm, pd = persian.from_gregorian(y, m, d)
    entries.append(("Persian/Jalali", f"{py}-{pm}-{pd}"))

    by, bq, bd = bahai.from_gregorian(y, m, d)
    entries.append(("Bahá'í", f"{by}-{bq}-{bd}"))

    iy2, im2, id2 = indian_civil.from_gregorian(y, m, d)
    entries.append(("Indian Civil", f"{iy2}-{im2}-{id2}"))

    baktun, katun, tun, uinal, kin = mayan.from_gregorian(y, m, d)
    entries.append(("Mayan Long Count", f"{baktun}.{katun}.{tun}.{uinal}.{kin}"))

    if RICH_AVAILABLE:
        console.print(Text("\nMulti-Calendar Conversion Utility", style="bold blue"))
        console.print(Text(header, style="cyan"))
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column("Calendar", style="magenta")
        table.add_column("Date", style="white")
        for name, value in entries:
            table.add_row(name, value)
        console.print(table)
        console.print(Text("Done.\n", style="dim"))
    else:
        print("\n=== Multi-Calendar Conversion Utility ===")
        print(header)
        print("----------------------------------------")
        for name, value in entries:
            print(f"{name}: {value}")
        print("----------------------------------------")
        print("Done.\n")


if __name__ == "__main__":
    main()
