import argparse
import re

weight_classification = {
    (0, 18.5): 'Underweight',
    (18.5, 25): 'Normal',
    (25, 30): 'Overweight',
    (30, 35): 'Obesity Class 1',
    (35, 40): 'Obesity Class 2',
    (40, float('inf')): 'Obesity Class 3'
}

def get_bmi_classification(bmi):
    for key in weight_classification:
        if key[0] <= bmi < key[1]:
            return weight_classification[key]
    return 'Unknown'

def kg_to_pounds(kg):
    return kg * 2.20462

def pounds_to_kg(pounds):
    return pounds / 2.20462

def stones_to_kg(stones, pounds=0):
    return stones * 6.35029 + pounds * 0.453592

def pounds_to_stones(pounds):
    stones = int(pounds // 14)
    pounds = int(pounds % 14)
    return stones, pounds

def cm_to_feet(cm):
    feet = int(cm // 30.48)
    inches = int((cm % 30.48) / 2.54)
    return feet, inches

def feet_to_cm(feet, inches=0):
    return feet * 30.48 + inches * 2.54

def get_bmi(cm, kg):
    return kg / (cm / 100) ** 2

def show_bmi_table(period="month", height=181, weight=84, gain=2.5, limit=12, bmi=None):

    if height and isinstance(height, str):
        match = re.match(r'(\d+)\'(\d+)"', height)
        if match:
            feet, inches = int(match.group(1)), int(match.group(2))
            height = feet_to_cm(feet, inches)
        else:
            print(f'Error: Invalid height: {height}')
            return
    else:
        feet, inches = cm_to_feet(height)

    if weight and isinstance(weight, str):
        if weight.endswith("lbs"):
            weight = pounds_to_kg(float(weight[:-3]))
        elif weight.endswith("st"):
            match = re.match(r'(\d+)st(\d+)?', weight)
            if match:
                stones, pounds = int(match.group(1)), int(match.group(2) or 0)
                weight = stones_to_kg(stones, pounds)
            else:
                print(f'Error: Invalid weight: {weight}')
                return

    if bmi and height:
        weight = bmi * (height / 100) ** 2
        print(f"Calculated weight from BMI and height: {weight:.2f} kg")

    if not height or not weight:
        print('Error: Height and weight must be provided.')
        return

    if height < 0 or weight < 0:
        print('Error: Height and weight must be positive.')
        return

    start_weight = weight
    start_bmi = get_bmi(height, weight)

    if not start_bmi or start_bmi < 10:
        print(f'Error: Invalid BMI.')
        return

    print(f'Height: {height:.1f} cm ({feet}\'{inches}")\tStart BMI: {start_bmi:.2f}\tStart Weight: {start_weight:.1f} kg')
    print(f'Gain: {gain:.1f} kg per {period} for {limit} {period}s.')

    for section in range(limit + 1):
        weight = start_weight + (gain * section)
        bmi = get_bmi(height, weight)
        classification = get_bmi_classification(bmi)
        stones, pounds = pounds_to_stones(kg_to_pounds(weight))
        print(f'{section:2}  {weight:>10.2f} kg   {stones:2} st {pounds:2} lbs    bmi: {bmi:.2f}    {classification}')

def parse_height(arg):
    if 'cm' in arg:
        return float(arg.replace('cm', ''))
    if 'f' in arg:
        match = re.match(r'(\d+)f(\d+)', arg)
        if match:
            feet, inches = int(match.group(1)), int(match.group(2))
            return feet_to_cm(feet, inches)
    if '\'' in arg:
        match = re.match(r'(\d+)\'(\d+)"', arg)
        if match:
            feet, inches = int(match.group(1)), int(match.group(2))
            return feet_to_cm(feet, inches)
    if 'm' in arg:
        return float(arg.replace('m', '')) * 100
    if 'inches' in arg:
        return float(arg.replace('inches', '')) * 2.54
    return None

def parse_weight(arg):
    if 'kg' in arg:
        return float(arg.replace('kg', ''))
    if 'lbs' in arg:
        return pounds_to_kg(float(arg.replace('lbs', '')))
    if 'st' in arg:
        match = re.match(r'(\d+)st(\d+)?', arg)
        if match:
            stones, pounds = int(match.group(1)), int(match.group(2) or 0)
            return stones_to_kg(stones, pounds)
    return None

def parse_bmi(arg):
    if 'bmi' in arg:
        return float(arg.replace('bmi', ''))
    return None

def main():
    parser = argparse.ArgumentParser(description='Calculate BMI progression')
    parser.add_argument('args', nargs='*', help='Arguments in the form of height and weight or BMI')
    parser.add_argument('-g', '--gain', type=float, help='Weight gain per period', default=2.5)
    parser.add_argument('-l', '--limit', type=int, help='Number of periods', default=12)
    parser.add_argument('-p', '--period', type=str, help='Period', default='month')
    args = parser.parse_args()

    height = None
    weight = None
    bmi = None

    for arg in args.args:
        parsed_height = parse_height(arg)
        if parsed_height is not None:
            height = parsed_height
            continue
        parsed_weight = parse_weight(arg)
        if parsed_weight is not None:
            weight = parsed_weight
            continue
        parsed_bmi = parse_bmi(arg)
        if parsed_bmi is not None:
            bmi = parsed_bmi
            continue

    if height and weight and bmi:
        print('Error: Only height and weight or BMI can be provided.')
    elif weight and bmi and not height:
        print('Error: Height is required if BMI and weight are provided.')
    elif height and bmi and not weight:
        weight = bmi * (height / 100) ** 2
    elif height and weight and not bmi:
        bmi = get_bmi(height, weight)

    show_bmi_table(period=args.period, height=height, weight=weight, bmi=bmi, gain=args.gain, limit=args.limit)

if __name__ == "__main__":
    main()
