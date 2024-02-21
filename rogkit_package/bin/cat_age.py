import sys

def cat_age_to_human(cat_age_years, cat_age_months=0):
    total_cat_age_months = cat_age_years * 12 + cat_age_months

    if total_cat_age_months <= 12:
        human_years = total_cat_age_months / 12 * 15
    elif total_cat_age_months <= 24:
        human_years = 15 + ((total_cat_age_months - 12) / 12 * 9)
    else:
        human_years = 24 + ((total_cat_age_months - 24) / 12 * 4)

    if human_years == int(human_years):
        human_years = int(human_years)

    return human_years

def main():
    # Check for at least one argument (beyond the script name)
    if len(sys.argv) < 2:
        print("Usage: cat_age <cat_age_years> [cat_age_months]")
        sys.exit(1)

    cat_age_years = float(sys.argv[1])
    cat_age_months = float(sys.argv[2]) if len(sys.argv) > 2 else 0

    human_years = cat_age_to_human(cat_age_years, cat_age_months)
    print(f"A cat that is {cat_age_years} years and {cat_age_months} months old is approximately {human_years:.2f} human years old.")

if __name__ == "__main__":
    main()
