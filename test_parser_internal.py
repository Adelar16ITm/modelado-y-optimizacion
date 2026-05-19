
from modules.lp_parser import LPParser
import sys

def test_parser(expr, expected_terms, description):
    print(f"Testing: {description}")
    print(f"Expression: {expr}")
    try:
        parser = LPParser(expr, []) # No constraints needed for expression test
        # Access private method for direct testing or just parse an objective
        # Let's parse as objective (which calls _parse_expression)
        parser.objective_str = expr
        # We need to bypass the "clean_obj" logic in parse() to test raw strings if we want
        # But let's test the public API: parse()
        
        # parse() expects "Max ..." or "Min ..."
        # If we just give the expression, it defaults to Min
        parser = LPParser(f"Max {expr}", [])
        result = parser.parse()
        
        coeffs = {}
        # result['original_c'] is an array corresponding to result['variables']
        for var, val in zip(result['variables'], result['original_c']):
            if abs(val) > 1e-9:
                coeffs[var] = val
                
        # Compare coeffs with expected
        # Expected format: {'a': 1000, 'b': 750 ...}
        
        # Check for missing or extra variables
        all_vars = set(coeffs.keys()) | set(expected_terms.keys())
        
        passed = True
        for var in all_vars:
            got = coeffs.get(var, 0)
            want = expected_terms.get(var, 0)
            if abs(got - want) > 1e-5:
                print(f"  [FAIL] Var {var}: Got {got}, Expected {want}")
                passed = False
        
        if passed:
            print("  [PASS]")
        else:
            print("  [FAIL]")
            
    except Exception as e:
        print(f"  [ERROR] {e}")

if __name__ == "__main__":
    print("--- Starting LP Parser Verification ---\n")
    
    # Test 1: Implicit Multiplication & Parentheses (User's Example)
    # 1000(a+d+g)+750(b+e+h)+250(c+f+i)
    # 1000a + 1000d + 1000g + 750b + ...
    test_parser(
        "1000(a+d+g)+750(b+e+h)+250(c+f+i)",
        {
            'a': 1000, 'd': 1000, 'g': 1000,
            'b': 750,  'e': 750,  'h': 750,
            'c': 250,  'f': 250,  'i': 250
        },
        "User Complex Example"
    )
    
    # Test 2: Standard Linear
    test_parser(
        "3x + 5y",
        {'x': 3, 'y': 5},
        "Standard Linear"
    )
    
    # Test 3: Distributive with Negative
    # 3(x+y) - 2(x-y) -> 3x + 3y - 2x + 2y -> x + 5y
    test_parser(
        "3(x+y) - 2(x-y)",
        {'x': 1, 'y': 5},
        "Distributive with Negative"
    )
    
    # Test 4: Implicit Multi: Number-Var
    # 2x + 4y
    test_parser(
        "2x + 4y",
        {'x': 2, 'y': 4},
        "Implicit 2x"
    )
    
    # Test 5: Implicit Multi: Parenthesis-Parenthesis (Not strictly required but good to check)
    # (2)x -> 2x? 
    # Current regex: (\))(\s*)([a-zA-Z_0-9\(]) -> \1*\3
    # (2)x -> (2)*x
    test_parser(
        "(2)x",
        {'x': 2},
        "Parens around coefficient"
    )
    
    print("\n--- Verification Complete ---")
