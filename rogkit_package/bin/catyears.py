"""
Cat age to human years converter.

Converts cat ages to equivalent human years using standard veterinary
age conversion formulas (15 for first year, 9 for second, 4 per year after).
"""
import sys
from .rounder import round_decimals


def cat_age_to_human(cat_age_years, cat_age_months=0):
    """
    Convert cat age to equivalent human years.
    
    Args:
        cat_age_years: Cat's age in years
        cat_age_months: Additional months (default: 0)
        
    Returns:
        Equivalent age in human years
    """
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
    """CLI entry point for cat age converter."""
    # Check for at least one argument (beyond the script name)
    if len(sys.argv) < 2:
        print("Usage: cat_age <cat_age_years> [cat_age_months]")
        sys.exit(1)

    cat_age_years = abs(float(sys.argv[1]))
    cat_age_months = abs(float(sys.argv[2])) if len(sys.argv) > 2 else 0

    human_years = cat_age_to_human(cat_age_years, cat_age_months)

    # Building the cat age string
    cat_parts = []
    if cat_age_years > 0:
        cat_parts.append(f'{round_decimals(cat_age_years, 0)} years')
    if cat_age_months > 0:
        cat_parts.append(f'{round_decimals(cat_age_months, 0)} months')

    cat_age_str = ' and '.join(cat_parts)
    if not cat_age_str:
        cat_age_str = "less than a month"  # For the case of 0 years and 0 months

    human = round_decimals(human_years, 1)

    print(f"A cat that is {cat_age_str} old is approximately {human} human years old.")


if __name__ == "__main__":
    main()
