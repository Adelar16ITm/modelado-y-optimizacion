def get_default_example():
    """Returns the mandatory test case."""
    return {
        "objective": "8x + 10y",
        "constraints": """x + y <= 1100
1/2x + 1/2y <= 600
2/3x + y <= 800
1/4x + 1/2y <= 375"""
    }

def get_more_examples():
    """Returns a dictionary of extra examples."""
    return {
        "Test Case (Mandatory)": get_default_example(),
        "Simple Manufacturing": {
            "objective": "20x + 30y",
            "constraints": """x <= 60
y <= 50
x + 2y <= 120"""
        },
        "Unbounded": {
            "objective": "x + y",
            "constraints": """x >= 5
y >= 5"""
        },
        "Infeasible": {
            "objective": "x + y",
            "constraints": """x + y <= 5
x + y >= 10"""
        }
    }
