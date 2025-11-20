"""
Genealogy calculator showing ancestral DNA percentages.

Calculates the number of ancestors and percentage of DNA shared
with each generation going back in time.
"""
import argparse
from .bignum import bignum

try:  # optional fancy output
    from rich.console import Console
    from rich.table import Table

    console = Console()
    RICH_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    console = None
    RICH_AVAILABLE = False


def calculate_dna_shared(generations):
    """Calculate the percentage of DNA shared with each generation back."""
    # Each generation back halves the DNA shared
    percentages = [(1 / (2 ** i)) * 100 for i in range(1, generations + 1)]
    return percentages

def parent_name(number):
    """Generate relationship name for a given generation number."""
    if number == 1:
        return "Parent"
    elif number == 2:
        return "Grandparent"
    else:
        return f"Great-{number - 2} Grandparent"

def main():
    """CLI entry point for genealogy calculator."""
    parser = argparse.ArgumentParser(description='Show the number of ancestors and percentage of DNA shared with each generation.')
    parser.add_argument('-g', '--generations', type=int, default=10, help='Number of generations to calculate (default: 10)')
    parser.add_argument('-y', '--years', type=int, default=25, help='Number of years per generation (default: 25)')
    args = parser.parse_args()

    # Number of generations to calculate
    generations = args.generations

    if generations > 1000:
        print('Showing max 1000 generations')
        generations = 1000

    # Calculate the DNA percentages
    percentages = calculate_dna_shared(generations)

    # Print the results
    rows = []
    for i, percentage in enumerate(percentages, start=1):
        years = i * args.years
        number_of_ancestors = bignum(2 ** i)
        rows.append(
            (
                str(i),
                str(years),
                f"{percentage:.03f}",
                parent_name(i),
                str(number_of_ancestors),
            )
        )

    if RICH_AVAILABLE:
        table = Table(box=None, pad_edge=False)
        table.add_column("Gen", justify="right", style="bold cyan")
        table.add_column("Years", justify="right")
        table.add_column("% DNA", justify="right", style="magenta")
        table.add_column("Relationship", style="green")
        table.add_column("Ancestors", justify="right", style="yellow")
        for row in rows:
            table.add_row(*row)
        console.print(table)
    else:
        print("Gen".ljust(5) + "Years".ljust(10) + "% DNA".ljust(10) + "Relationship".ljust(25) + "Ancestors".ljust(20))
        for row in rows:
            print(
                f"{row[0].ljust(5)}"
                f"{row[1].ljust(10)}"
                f"{row[2].ljust(10)}"
                f"{row[3].ljust(25)}"
                f"{row[4].ljust(20)}"
            )

if __name__ == "__main__":
    main()
