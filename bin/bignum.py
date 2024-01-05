#!/usr/bin/env python3
import dataclasses
import argparse

@dataclasses.dataclass
class PrettyNumberFormatter:
    BIGNUM_ZEROS = (
        (100, 'googol'),
        (63, 'vigintillion'),
        (60, 'novemdecillion'),
        (57, 'octodecillion'),
        (54, 'sedecillion'),
        (51, 'sedecillion'),
        (48, 'quindecillion'),
        (45, 'quattuordecillion'),
        (42, 'tredicillion'),
        (39, 'duodecilion'),
        (36, 'unidecillion'),
        (33, 'decillion'),
        (30, 'nonillion'),
        (27, 'octillion'),
        (24, 'septillion'),
        (21, 'sextillion'),
        (18, 'quintillion'),
        (15, 'quadrillion'),
        (12, 'trillion'),
        (9, 'billion'),
        (6, 'million'),
        (3, 'thousand'),
        (2, 'hundred'),
    )

    intervals = (
        ('years', 31557600),
        ('months', 2592000),
        ('weeks', 604800),
        ('days', 86400),
        ('hours', 3600),
        ('minutes', 60),
        ('seconds', 1),
    )

    @staticmethod
    def prettynumber(number):
        if type(number) == str and number.isdigit():
            number = int(number)
        try:
            return f'{number:,}'
        except:
            pass
        return number

    def list_bignums(self, name=None):
        result = []
        for i in reversed(self.BIGNUM_ZEROS):
            result.append(f'1 with {i[0]} zeros is a {i[1]} (1e+{i[0]}).')
        return result

    def zillions(self, number, round_to=2,show_e=2,minimum=1000):
        '''
        Return a human-readable version of a very large number
        :param number: the number to convert (can be string in scientific format)
        :param round_to: round quotiant of exponant to 2 significant figures
        :param show_e: show scientific notation if number above 10**e.
        :param minimum: the smallest number to convert to text
        :return: a pretty text string
        '''
        try:
            if 'e+' in number:
                quot, expo = number.split('e+')
                if int(expo) > 310:
                    return number
                number = float(quot) * (10 ** int(expo))
        except:
            pass
        if not isinstance(number, (int, float)):
            try:
                number=float(number.replace(',',''))
            except:
                pass
        if not number:
            "None"
        if not isinstance(number, (int, float)) or number < minimum:
            return number
        description = ''
        if show_e and number >= (10 ** show_e) :
            e = f'{number:e}'
            e = e[e.find('e'):]
            e = f'({e})'
        else:
            e = ''
        for i in self.BIGNUM_ZEROS:
            factor = 10 ** int(i[0])
            if number >= factor:
                number /= factor
                description = i[1] + ' ' + description
        # Only show round_to significant digits if they are not zero
        rounded = round(number)
        if round_to:
            rounded_to = round(number,round_to)
            if rounded != rounded_to:
                rounded = rounded_to
        return f'{rounded} {description}{e}'.strip()

    def seconds_time(self, seconds, granularity=2):
        result = []

        if seconds > 31557600 * 10:
            return f'{self.zillions(int(seconds / 31557600))} years'

        for name, count in self.intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append("{} {}".format(int(value), name))
        result = ', '.join(result[:granularity])
        words = result.split()
        if len(words)>3:
            words[-3] = words[-3].replace(',',' and')
        result = ' '.join(words)
        return result
    
def demo_uses():
    formatter = PrettyNumberFormatter()
    formatted_number = formatter.prettynumber(1234567890)
    print(formatted_number)  # Output: '1,234,567,890'

    big_numbers = formatter.list_bignums()
    for big_number in big_numbers:
        print(big_number)
    # Output will include: '1 with 100 zeros is a googol (1e+100).', etc.

    readable_large_number = formatter.zillions(1e23)
    print(readable_large_number)  # Output might be something like '10 vigintillion'

    time_description = formatter.seconds_time(1000000000)  # 1 billion seconds
    print(time_description)  # Output: '31 years and 8 months', depending on the granularity

def bignum(number, round_to=2, show_e=2, minimum=1000):
    try:
        formatter = PrettyNumberFormatter()
        return formatter.zillions(number, round_to=round_to, show_e=show_e, minimum=minimum)
    except Exception as e:
        print(f"Error converting number to text: {e}")
        return f'{number:,}'

def seconds_time(seconds, granularity=2):
    formatter = PrettyNumberFormatter()
    return formatter.seconds_time(seconds, granularity=granularity)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Convert a number to a human-readable format.')
    parser.add_argument('number', type=str, nargs='?', help='Number to convert')
    parser.add_argument('-b', '--bignums', action='store_true', help='List big numbers')
    parser.add_argument('-p', '--pretty', action='store_true', help='Show pretty number')
    parser.add_argument('-s', '--seconds', type=int, help='Convert seconds to human-readable format')
    parser.add_argument('-d', '--demo', action='store_true',  help='Show demo of uses')
    parser.add_argument('-r', '--round', type=int, default=2, help='Round to this many significant figures')
    parser.add_argument('-e', '--show-e', type=int, default=2, help='Show scientific notation if number above 10**e')
    parser.add_argument('-m', '--minimum', type=int, default=1000, help='The smallest number to convert to text')
    return parser.parse_args()

def main():
    args = parse_arguments()

    # If no arguments are provided, show help
    if not any(vars(args).values()):
        print("No arguments provided. Use -h or --help for usage information.")
        return

    formatter = PrettyNumberFormatter()

    # Handle demo
    if args.demo:
        demo_uses()
        return

    # Handle seconds conversion
    if args.seconds is not None:
        print(formatter.seconds_time(args.seconds))
        return

    # Handle pretty number
    if args.pretty and args.number:
        print(formatter.prettynumber(args.number))
        return

    # Handle big numbers listing
    if args.bignums:
        big_numbers = formatter.list_bignums()
        for big_number in big_numbers:
            print(big_number)
        return

    # Handle zillions conversion
    if args.number:
        print(formatter.zillions(args.number, round_to=args.round, show_e=args.show_e, minimum=args.minimum))
        return

    # Default case - Show help if no relevant option is provided
    print("Invalid or insufficient arguments. Use -h or --help for usage information.")

if __name__ == "__main__":
    main()
