from logic.parser import parse_full_input, parse_term

obj = "3x + 5y"
cons = """x + y <= 10
2x + y <= 15
x >= 2"""

print(f"Testing Objective: '{obj}'")
print(f"Testing Constraints:\n{cons}")

print("\n--- Parsing ---")
res = parse_full_input(obj, cons)
print("Result Keys:", res.keys())
print("Variables:", res.get('variables'))
print("Errors:", res.get('errors'))
print("Objective coeffs:", res.get('c'))

print("\n--- Individual Term Debug ---")
terms = ["3x", "5y", "x", "-y"]
for t in terms:
    print(f"'{t}' -> {parse_term(t)}")
