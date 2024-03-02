import random
import argparse

def throw_dice(number = 1, sides = 6):
    result = []
    for _ in range(number):
        result.append(random.randint(1, sides))
    return result

def main():
    parser = argparse.ArgumentParser(description='Throw dice.')
    parser.add_argument('-n', '--number', type=int, default=1, help='Number of dice to throw.')
    parser.add_argument('-s', '--sides', type=int, default=6, help='Number of sides on the dice.')
    args = parser.parse_args()

    result = throw_dice(args.number, args.sides)
    print(result)

if __name__ == "__main__":
    main()  