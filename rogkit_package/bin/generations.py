import argparse

# Function to calculate the percentage of DNA shared with each generation
def calculate_dna_shared(generations):
    # Each generation back halves the DNA shared
    percentages = [(1 / (2 ** i)) * 100 for i in range(1, generations + 1)]
    return percentages

def parent_name(number):
    if number == 1:
        return "Parent"
    elif number == 2:
        return "Grandparent"
    else:
        return f"Great-{number - 2} Grandparent"

def main():
    parser = argparse.ArgumentParser(description='Calculate the percentage of DNA shared with each generation.')
    parser.add_argument('-g', '--generations', type=int, default=10, help='Number of generations to calculate (default: 10)')
    parser.add_argument('-y', '--years', type=int, default=25, help='Number of years per generation (default: 25)')
    args = parser.parse_args()

    # Number of generations to calculate
    generations = args.generations

    # Calculate the DNA percentages
    percentages = calculate_dna_shared(generations)

    # Print the results
    print("Gen".ljust(5) + "Years".ljust(10) + "% DNA".ljust(10) + "Ancestors".ljust(20) + "Relationship".ljust(20))
    for i, percentage in enumerate(percentages, start=1):
        years = i * args.years  
        number_of_ancestors = 2 ** i
        print(f"{str(i).ljust(5)}{str(years).ljust(10)}{str(f'{percentage:.03f}').ljust(10)}{str(f'{number_of_ancestors:,}').ljust(20)}{parent_name(i).ljust(20)}")

if __name__ == "__main__":
    main()
