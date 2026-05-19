import textwrap

def get_template(name):
    """
    Returns (objective_str, constraints_str) for the selected template.
    """
    if name == "Generic (Abstract)":
        return _generic_template()
    elif name == "Diet/Mix Problem":
        return _diet_problem()
    elif name == "Manpower (Shifts)":
        return _manpower_problem()
    elif name == "Transportation":
        return _transportation_problem()
    elif name == "Blending (Gasoline)":
        return _blending_problem()
    elif name == "Financial Planning":
        return _financial_planning()
    elif name == "Credit Portfolio":
        return _credit_portfolio()
    else:
        return "", ""

def _generic_template():
    obj = "3x + 5y"
    const = textwrap.dedent("""\
        x + y <= 10
        2x + y <= 15
        x >= 2
        """)
    return obj, const

def _diet_problem():
    # Min Cost. Foods: Corn (x), Soy (y).
    # Cost: Corn $0.3, Soy $0.9
    # Nutrient 1: Corn 10, Soy 50 >= 1000
    # Nutrient 2: Corn 20, Soy 10 >= 800
    obj = "0.3x + 0.9y"
    const = textwrap.dedent("""\
        10x + 50y >= 1000  # Protein
        20x + 10y >= 800   # Vitamin
        x + y <= 150       # Max Weight
        """)
    return obj, const

def _manpower_problem():
    # 3 Shifts: x1 (8-16), x2 (16-24), x3 (0-8)
    # Demand: 8-12(10), 12-16(8), 16-20(15), 20-24(12), 0-4(6), 4-8(5)
    # Simplified: x1 covers 8-16. 
    # Let's use standard overlapping shifts example from textbooks.
    # Shifts start every 4 hours, last 8 hours.
    # x1: 0-8, x2: 4-12, x3: 8-16, x4: 12-20, x5: 16-24, x6: 20-4
    # Min total workers
    obj = "x1 + x2 + x3 + x4 + x5 + x6"
    const = textwrap.dedent("""\
        x6 + x1 >= 5   # 00:00 - 04:00
        x1 + x2 >= 10  # 04:00 - 08:00
        x2 + x3 >= 14  # 08:00 - 12:00
        x3 + x4 >= 8   # 12:00 - 16:00
        x4 + x5 >= 12  # 16:00 - 20:00
        x5 + x6 >= 6   # 20:00 - 24:00
        """)
    return obj, const

def _transportation_problem():
    # Sources: S1(150), S2(200). Dest: D1(110), D2(130), D3(110).
    # Vars: x_ij
    # Cost: C_ij (matrix)
    obj = "10x_11 + 12x_12 + 15x_13 + 13x_21 + 10x_22 + 11x_23"
    const = textwrap.dedent("""\
        # Supply
        x_11 + x_12 + x_13 <= 150
        x_21 + x_22 + x_23 <= 200
        
        # Demand
        x_11 + x_21 >= 110
        x_12 + x_22 >= 130
        x_13 + x_23 >= 110
        """)
    return obj, const

def _blending_problem():
    # Gasoline Blending
    # Inputs: CrudeA (x), CrudeB (y)
    # Octane: A(80), B(90). Target >= 87.
    # Sulfur: A(0.02), B(0.01). Target <= 0.015.
    # Max Supply: 1000 each.
    # Profit: sell price 5 - cost A(3) - cost B(4) -> Maximize relevant margin?
    # Simple Max Profit: 2x + 1y (assuming margins)
    # Octane Constr: (80x + 90y)/(x+y) >= 87 => 80x + 90y >= 87(x+y) => -7x + 3y >= 0
    obj = "2x + 1y"
    const = textwrap.dedent("""\
        -7x + 3y >= 0    # Octane >= 87
        0.005x - 0.005y <= 0 # Sulfur <= 0.015 (Simplified: 0.02x+0.01y <= 0.015(x+y))
        x <= 1000        # Supply A
        y <= 1000        # Supply B
        """)
    return obj, const

def _financial_planning():
    # Multi-period investment
    # A(Inv Year 1, ret 1.3 in Y3), B(Inv Y2, ret 1.4 in Y4)
    # S(Savings, 1.05 per year)
    # Cashflow constraints.
    obj = "1.05s3 + 1.3x1" # Maximize cash at end of Y3 (Horizon)
    const = textwrap.dedent("""\
        x1 + s1 <= 10000        # Year 1 Start
        -0.5x1 + x2 + s2 - 1.05s1 = 0  # Year 2 Balance (x1 pays back part? Hypothetical)
        -1.3x1 - 1.4x2 + s3 - 1.05s2 = 0 # Year 3 Balance
        """)
    return obj, const

def _credit_portfolio():
    # Bank Loans: Personal(x1), Car(x2), Home(x3), Farm(x4), Commercial(x5)
    # Returns: 0.14, 0.13, 0.11, 0.125, 0.10
    # Bad Debt: 0.10, 0.07, 0.03, 0.05, 0.02. Max Avg Bad Debt <= 0.04
    # Diversity: Home >= 40% total usually.
    # Allocation: x3 >= 0.40(Sum x) => 0.6x3 - 0.4x1 - 0.4x2 - 0.4x4 - 0.4x5 >= 0
    obj = "0.14x1 + 0.13x2 + 0.11x3 + 0.125x4 + 0.10x5"
    const = textwrap.dedent("""\
        x1 + x2 + x3 + x4 + x5 <= 1000000  # Budget
        
        # Risk (Bad debt <= 4%)
        # 0.10x1 + 0.07x2 + 0.03x3 + 0.05x4 + 0.02x5 <= 0.04(Total)
        0.06x1 + 0.03x2 - 0.01x3 + 0.01x4 - 0.02x5 <= 0
        
        # Diversity
        -0.4x1 - 0.4x2 + 0.6x3 - 0.4x4 - 0.4x5 >= 0 # Home loans >= 40%
        x4 + x5 <= 300000 # Commercial/Farm limit
        """)
    return obj, const
