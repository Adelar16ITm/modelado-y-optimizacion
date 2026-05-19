
import ast
import re

class LinearExpressionExpander:
    def __init__(self):
        self.variables = set()

    def expand(self, expression):
        # 1. Normalization: Implicit Multiplication
        # Order matters!
        
        # a) Number followed by Variable or Open Parenthesis
        # We need to be careful with scientific notation (e.g. 1e10 is valid, 1e is not).
        # But 'e' is also a variable name. 
        # For simplicity, if we assume standard int/float like 1000 or 0.5:
        # 1000a -> 1000*a
        # 1000( -> 1000*(
        
        # Regex for simple numbers (no scientific notation for now to avoid '2e3' issues vs '2e')
        # match digit, then optional space, then (letter or paren)
        expression = re.sub(r'(\d)(\s*)([a-zA-Z_\(])', r'\1*\3', expression)
        
        # b) Close Parenthesis followed by Number or Variable or Open Parenthesis
        # (a)b -> (a)*b
        # (a)2 -> (a)*2
        # (a)(b) -> (a)*(b)
        expression = re.sub(r'(\))(\s*)([a-zA-Z_0-9\(])', r'\1*\3', expression)
        
        # 2. Parse using Python AST
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            raise ValueError(f"Syntax Error in expression: {e}")
            
        # 3. Process AST
        result_terms = self._process_node(tree.body)
        
        # 4. Format Output
        # Combine terms: {var: coeff}
        final_coeffs = {}
        const_val = 0
        
        for term in result_terms:
            # Term is (coeff, var_name)
            # var_name None means constant
            c, v = term
            if v is None:
                const_val += c
            else:
                final_coeffs[v] = final_coeffs.get(v, 0) + c
                self.variables.add(v)
                
        # Build string
        output_parts = []
        for var in sorted(final_coeffs.keys()):
            coeff = final_coeffs[var]
            if coeff == 0: continue
            
            # Format
            if coeff == 1:
                s = f"+{var}"
            elif coeff == -1:
                s = f"-{var}"
            else:
                s = f"{coeff:+.4g}{var}" 
            output_parts.append(s)
            
        if const_val != 0:
            output_parts.append(f"{const_val:+.4g}")
            
        return "".join(output_parts).lstrip('+')

    def _process_node(self, node):
        """
        Returns a list of terms: [(coeff, params)...] where term is just (coeff, variable_name) 
        Linear expressions only, so no (var, var)
        """
        if isinstance(node, ast.BinOp):
            left = self._process_node(node.left)
            right = self._process_node(node.right)
            
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                # Negate right
                radj = [(c * -1, v) for c, v in right]
                return left + radj
            elif isinstance(node.op, ast.Mult):
                # Distribute
                # One side must be constant (scalar) for it to be linear
                # If both have variables -> Quadratic (Error)
                
                left_is_const = all(v is None for c, v in left)
                right_is_const = all(v is None for c, v in right)
                
                if left_is_const:
                    scalar = sum(c for c, v in left)
                    return [(c * scalar, v) for c, v in right]
                elif right_is_const:
                    scalar = sum(c for c, v in right)
                    return [(c * scalar, v) for c, v in left]
                else:
                    raise ValueError("Non-linear multiplication detected (Variable * Variable)")
            elif isinstance(node.op, ast.Div):
                 # Division by constant allowed
                right_is_const = all(v is None for c, v in right)
                if not right_is_const:
                     raise ValueError("Division by variable not allowed")
                divisor = sum(c for c, v in right)
                if divisor == 0: raise ValueError("Division by zero")
                return [(c / divisor, v) for c, v in left]
                
        elif isinstance(node, ast.UnaryOp):
            operand = self._process_node(node.operand)
            if isinstance(node.op, ast.USub):
                return [(c * -1, v) for c, v in operand]
            elif isinstance(node.op, ast.UAdd):
                return operand
                
        elif isinstance(node, ast.Name):
            return [(1.0, node.id)]
            
        elif isinstance(node, ast.Constant): # Python 3.8+
            return [(node.value, None)]
            
        elif isinstance(node, ast.Num): # Python <3.8
            return [(node.n, None)]
            
        raise ValueError(f"Unsupported syntax: {type(node)}")

# Test
expander = LinearExpressionExpander()
expressions = [
    "1000(a+d+g)+750(b+e+h)+250(c+f+i)",
    "3(x + 2y) - 5(z - 2w)",
    "2x",
    "x + y",
    "-2(x - 5)",
    "0.5(x + y)"
]

for e in expressions:
    print(f"Original: {e}")
    try:
        res = expander.expand(e)
        print(f"Expanded: {res}")
    except Exception as err:
        print(f"Error: {err}")
    print("-" * 20)
