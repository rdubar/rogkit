import argparse

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

def pounds_to_stones(pounds):
    stones = int(pounds // 14)
    pounds = int(pounds % 14)
    return stones, pounds

def cm_to_feet(cm):
    feet = int(cm // 30.48)
    inches = int((cm % 30.48) / 2.54)
    return feet, inches

def get_bmi(cm, kg):
    return kg / (cm / 100) ** 2

def show_bmi_table(period="month",
                   height=165,  # in cm
                   feet=None,  # e.g., "5.2" for 5 feet 2 inches
                   weight=51,  # in kg
                   gain=2.5,  # kg per period
                   limit=24,  # number of periods
                   bmi=None):

    if feet:
        try:
            feet, inches = feet.split(".")
            height = (int(feet) * 30.48) + (int(inches) * 2.54)
        except ValueError:
            print(f'Error: Invalid feet and inches format: {feet}')
            return

    if height and isinstance(height, str) and "'" in height:
        # assume height is in feet and inches
        feet, inches = height.split("'")
        try:
            height = (int(feet) * 30.48) + (int(inches) * 2.54)
        except ValueError:
            print(f'Error: Invalid height: {height}')
            return
    else:
        feet, inches = cm_to_feet(height)
    
    if weight and weight < 25:
        # assume weight is in stones and pounds
        stones = weight
        try:
            weight = stones * 14
        except ValueError:
            print(f'Error: Invalid weight: {weight}')
            return
        print(f'Weight: {stones} st')
        
    if bmi and height and weight:
        print("BMI, height and weight are all set. Ignoring BMI.")
        bmi = None
    elif bmi and height and not weight:
        weight = bmi * (height / 100) ** 2
    elif bmi and weight and not height:
        height = weight / bmi ** 0.5
        
    if not bmi and not height and not weight:
        print('Error: No height, weight or BMI provided.')
        return
    
    if height < 0 or weight < 0:
        print('Error: Height and weight must be positive.')
        return

    start_weight = weight
    start_bmi = bmi or get_bmi(height, weight)
    
    if not start_bmi or start_bmi < 10:
        print(f'Error: Invalid BMI.')
        return
    
    print(f'Height: {height} cm ({feet}\'{inches}")\tStart BMI: {start_bmi:.2f}\tStart Weight: {start_weight} kg')
    print(f'Gain: {gain} kg per {period} for {limit} {period}s.')
    
    for section in range(limit+1):
        weight = start_weight + (gain * section)
        bmi = get_bmi(height, weight)
        classification = get_bmi_classification(bmi)
        stones, pounds = pounds_to_stones(kg_to_pounds(weight))
        print(f'{section:2}  {weight:>10.2f} kg   {stones:2} st {pounds:2} lbs    bmi: {bmi:.2f}    {classification}')

def main():
    parser = argparse.ArgumentParser(description='Calculate BMI progression')
    parser.add_argument('-H', '--height', type=int, help='Height in cm', default=165)
    parser.add_argument('-f', '--feet', type=str, help='Height in feet and inches (e.g., 5.2 is 5 feet 2 inches)')
    parser.add_argument('-w', '--weight', type=int, help='Weight in kg', default=51)
    parser.add_argument('-b', '--bmi', type=float, help='BMI')
    parser.add_argument('-g', '--gain', type=float, help='Weight gain per period', default=2.5)
    parser.add_argument('-l', '--limit', type=int, help='Number of periods', default=12)
    parser.add_argument('-p', '--period', type=str, help='Period', default='month')
    args = parser.parse_args()
    show_bmi_table(period=args.period, height=args.height, feet=args.feet, weight=args.weight, bmi=args.bmi, gain=args.gain, limit=args.limit)
    
if __name__ == "__main__":
    main()
