"""
BMI (Body Mass Index) calculator and progression tracker.

Calculates BMI from height and weight, shows weight classifications,
and projects BMI changes over time with weight gain/loss.
"""
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
    """Get weight classification category based on BMI value."""
    for key in weight_classification:
        if key[0] <= bmi < key[1]:
            return weight_classification[key]
    return 'Unknown'

def kg_to_pounds(kg):
    """Convert kilograms to pounds."""
    return kg * 2.20462262185


def pounds_to_kg(pounds):
    """Convert pounds to kilograms."""
    return pounds / 2.20462262185


def stones_to_kg(stones, pounds=0):
    """Convert stones (and optional pounds) to kilograms."""
    return stones * 6.35029318 + pounds * 0.45359237


def pounds_to_stones(pounds):
    """Convert pounds to stones and remaining pounds."""
    stones = pounds // 14
    pounds = pounds % 14
    return stones, pounds


def cm_to_feet(cm):
    """Convert centimeters to feet and inches."""
    if not cm:
        return 0, 0
    total_inches = cm / 2.54
    feet = total_inches // 12
    inches = total_inches % 12
    return int(feet), round(inches, 2)

def feet_to_cm(feet, inches=0):
    """Convert feet and inches to centimeters."""
    return feet * 30.48 + inches * 2.54


def get_bmi(cm, kg):
    """Calculate BMI from height in cm and weight in kg."""
    return kg / (cm / 100) ** 2


def show_bmi_table(period="month", height=181, weight=84, gain=2.5, limit=12, bmi=None):
    """
    Display BMI progression table over time.
    
    Args:
        period: Time period for weight change (default: "month")
        height: Height in cm (or feet'inches" format string)
        weight: Starting weight in kg (or "lbs"/"st" format string)
        gain: Weight change per period in kg
        limit: Number of periods to project
        bmi: Optional BMI to calculate weight from
    """

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

    if not weight and bmi and height:
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

    print(f'Height: {height:.1f} cm ({feet}\'{inches:.0f}")\tStart BMI: {start_bmi:.2f}\tStart Weight: {start_weight:.1f} kg')
    print(f'Gain: {gain:.1f} kg per {period} for {limit} {period}s.')

    for section in range(limit + 1):
        weight = start_weight + (gain * section)
        bmi = get_bmi(height, weight)
        classification = get_bmi_classification(bmi)
        stones, pounds = pounds_to_stones(kg_to_pounds(weight))
        print(f'{section:2}  {weight:>8.2f} kg   {int(stones):>2} st {pounds:2.0f} lbs   bmi: {bmi:5.2f}   {classification:<15}')


def main():
    """CLI entry point for BMI calculator."""
    parser = argparse.ArgumentParser(description='Calculate BMI progression')
    parser.add_argument('args', nargs='*', help='Arguments in the form of height and weight or BMI')
    parser.add_argument('-g', '--gain', type=float, help='Weight gain per period', default=1)
    parser.add_argument('-l', '--limit', type=int, help='Number of periods', default=12)
    parser.add_argument('-p', '--period', type=str, help='Period', default='month')
    args = parser.parse_args()

    height = None
    weight = None
    bmi = None
    feet = False
    
    print('BMI Progression Calculator')
    
    if not args.args:
        print('Provide <height> <weight>, or e.g, <height> 0 <bmi> to calculate weight from BMI')
        return

    for arg in args.args:
        if arg == '_':
            arg = 0
        try:
            value = float(arg)
        except ValueError:
            print(f'Error: Invalid argument: {arg}')
            continue
        if height is None:
            if value == 0:
                height = 0
            elif value < 3:
                # assume it's meters
                height = value * 100
                print(f'Converting {arg} meters to {height} cm')
            elif value < 10:
                feet = True
                # assume it's feet dot inches
                if '.' in arg:
                    feet, inches = arg.split('.')
                else:
                    feet, inches = value, 0
                height = feet_to_cm(int(feet), int(inches))
                print(f'Converting {int(feet)}\'{inches}" to {height:.02f} cm.')
            elif value < 100:
                print(f'Error: Invalid height: {value} cm')
                return
            else:
                # assume it's cm
                height = value
                if height != 0:
                    print(f'Height: {height} cm')
        elif weight is None:
            if value == 0:
                weight = 0
                continue
            if value < 30:
                # assume weight is in stones dot pounds
                if '.' in arg:
                    stones, pounds = arg.split('.')
                else:
                    stones, pounds = value, 0
                weight = stones_to_kg(int(stones), int(pounds))    
                print(f'Converting {arg}st {pounds}lbs to {weight:.02f} kg')
                continue 
            if feet:
                # check if weight is in pounds
                pounds = pounds_to_kg(value)
                if height:
                    provisional_bmi = get_bmi(height, pounds)
                    if provisional_bmi > 15:
                        # assume it's pounds
                        weight = pounds_to_kg(value)
                        print(f'Converting {arg} pounds to {weight:.02f} kg')
                        continue
            # else
            weight = value
            print(f'Weight: {weight:.2f} kg')
        elif bmi is None and (height==0 or weight==0):
            bmi = float(arg)
            print(f'BMI: {bmi}')
            # stop processing further arguments
            break

    if height and weight and bmi:
        print('Error: Only height and weight or BMI can be provided.')
    elif weight and bmi and not height:
        height = (weight / bmi) ** 0.5 * 100
        print(f'Calculated height from BMI and weight: {height:.1f} cm')
    elif height and bmi and not weight:
        weight = bmi * (height / 100) ** 2
        print(f'Calculated weight from BMI and height: {weight:.2f} kg')
    elif height and weight and not bmi:
        bmi = get_bmi(height, weight)
        print(f'Calculated BMI from height and weight: {bmi:.2f}')
        
    if height < 50 or height > 300 or weight < 10 or weight > 500:
        print('Error: Height and weight must be within valid ranges.')
        return
        
    show_bmi_table(period=args.period, height=height, weight=weight, bmi=bmi, gain=args.gain, limit=args.limit)

if __name__ == "__main__":
    main()
