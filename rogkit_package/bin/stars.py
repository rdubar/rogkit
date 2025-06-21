def print_stars(count, char='*'):
    """Print a line of stars based on the count."""
    if count < 0:
        raise ValueError("Count must be a non-negative integer.")
    print(char * count)
    
def main():
    import argparse

    parser = argparse.ArgumentParser(description='Print a line of stars based on the count provided.')
    parser.add_argument('count', type=int, nargs='?', default=10, help='Number of stars to print (default: 10)')
    parser.add_argument('-t', '--tree', action='store_true', help='Print a tree of stars instead of a line')
    args = parser.parse_args()
    
    if args.tree:
        # If tree option is selected, print a tree of stars
        for i in range(1, args.count + 1):
            print(' ' * (args.count - i) + '*' * (2 * i - 1))
        return

    try:
        print_stars(args.count)
    except ValueError as e:
        print(f"Error: {e}")
        
        
if __name__ == "__main__":
    main()
#     main()
#     main()
