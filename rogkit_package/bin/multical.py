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

    print("\n=== Multi-Calendar Conversion Utility ===")
    print(f"Input Gregorian date: {y:04d}-{m:02d}-{d:02d}")
    print("----------------------------------------")

    # Gregorian
    print(f"Gregorian: {y}-{m}-{d}")

    # Julian
    jy, jm, jd = julian.from_gregorian(y, m, d)
    print(f"Julian: {jy}-{jm}-{jd}")

    # Hebrew calendar
    hy, hm, hd = hebrew.from_gregorian(y, m, d)
    print(f"Hebrew: {hy}-{hm}-{hd}")

    # Islamic (Tabular)
    iy, im, id_ = islamic.from_gregorian(y, m, d)
    print(f"Islamic (Tabular): {iy}-{im}-{id_}")

    # # Islamic (Umm al-Qura)
    # if islamic_umalqura and hasattr(islamic_umalqura, "from_gregorian"):
    #     try:
    #         iu_y, iu_m, iu_d = islamic_umalqura.from_gregorian(y, m, d)
    #         print(f"Islamic (Umm al-Qura): {iu_y}-{iu_m}-{iu_d}")
    #     except ValueError:
    #         print("Islamic (Umm al-Qura): date out of supported range")
    # else:
    #     print("Islamic (Umm al-Qura): support not available in convertdate")

    # Persian (Jalali)
    py, pm, pd = persian.from_gregorian(y, m, d)
    print(f"Persian/Jalali: {py}-{pm}-{pd}")

    # Baha'i calendar
    by, bq, bd = bahai.from_gregorian(y, m, d)
    print(f"Bahá'í: {by}-{bq}-{bd}")

    # Indian Civil calendar
    iy2, im2, id2 = indian_civil.from_gregorian(y, m, d)
    print(f"Indian Civil: {iy2}-{im2}-{id2}")

    # Mayan calendar (Long Count)
    baktun, katun, tun, uinal, kin = mayan.from_gregorian(y, m, d)
    print(f"Mayan Long Count: {baktun}.{katun}.{tun}.{uinal}.{kin}")

    print("----------------------------------------")
    print("Done.\n")


if __name__ == "__main__":
    main()
