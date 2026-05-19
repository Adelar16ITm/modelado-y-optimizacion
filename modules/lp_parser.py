import re
import ast
from fractions import Fraction
import numpy as np

class LPParser:
    def __init__(self, objective_str, constraints_list, optimization_type=None):
        self.objective_str = objective_str
        self.constraints_list = [c.strip() for c in constraints_list if c.strip()]
        self.variables = set()
        self.parsed_constraints = []
        self.objective_coeffs = {}
        # Allow explicit type override, otherwise default to min or auto-detect
        self.optimization_type = optimization_type.lower() if optimization_type else None
        
    def _parse_expression(self, expr):
        """
        Parses an expression like "3x + 2y - 0.5z" into a dict {var: coeff}.
        Handles fractions like "1/2x".
        """
        # 0. Expand Parentheses and Implicit Multiplication (AST-based)
        try:
            expr = self._expand_expression_ast(expr)
        except Exception as e:
            # Fallback or re-raise if AST fails? 
            # For now, let's assume if AST fails, the regex parser might also fail or produce wrong results
            # but maybe the user entered something valid for regex but not AST (unlikely given the new requirements).
            # We'll log/print error for debug but let it flow to regex for now? 
            # No, user requirements are strict about correct math. Raise error.
            raise ValueError(f"Error parsing expression structure: {e}")

        expr = expr.replace(' ', '')
        # Regex to capture terms: (+/-)(coefficient)(variable)
        # We need to be careful with things like "x" (coeff 1), "-x" (coeff -1)
        
        # Add a + at start if no sign
        if not expr.startswith('+') and not expr.startswith('-'):
            expr = '+' + expr
            
        # Regex explanation:
        # ([+-])?: match sign
        # ((?:\d+(?:/\d+)?|\d*\.\d+))?: match coefficient (fraction or float) or empty
        # ([a-zA-Z]\w*(\[[^\]]+\])?): match variable name (including simple array notation)
        term_pattern = re.compile(r'([+-])((?:\d+/\d+|\d*\.?\d+))?([a-zA-Z_]\w*(?:\[[^\]]+\])?)')
        
        terms = term_pattern.findall(expr)
        
        coeffs = {}
        for sign, coeff_str, var_name in terms:
            if not var_name: 
                continue # Skip if no variable
            
            # Determine numerical value of coefficient
            if not coeff_str:
                val = 1.0
            elif '/' in coeff_str:
                val = float(Fraction(coeff_str))
            else:
                val = float(coeff_str)
                
            if sign == '-':
                val = -val
                
            self.variables.add(var_name)
            coeffs[var_name] = coeffs.get(var_name, 0) + val
            
        return coeffs

    def _expand_expression_ast(self, expression):
        """
        Uses Python AST to expand distributive property and implicit multiplication.
        Converts "3(x + 2y)" -> "3x + 6y".
        """
        # 1. Normalization: Implicit Multiplication
        # a) Number followed by Variable or Open Parenthesis (e.g., 2x, 2(..) )
        # IMPORTANT: Do NOT insert '*' for scientific notation like 9e3 or 1.5E-4
        # Pattern: digit followed by e/E and then a digit = scientific notation → skip
        expression = re.sub(r'(\d)(\s*)([a-df-zA-DF-Z_\(])', r'\1*\3', expression)  # skip e/E
        # Also handle 'e'/'E' not followed by a digit (e.g., 9ez → 9*ez)
        expression = re.sub(r'(\d)(\s*)([eE])(?!\d)', r'\1*\3', expression)
        
        # b) Close Parenthesis followed by Number, Variable, or Open Parenthesis
        expression = re.sub(r'(\))(\s*)([a-zA-Z_0-9\(])', r'\1*\3', expression)
        
        # 2. Parse using Python AST
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
             # Basic regex fallback might have been better for "2x", but "2(x+y)" needs this.
             # If strict syntax fails, maybe it's already simple? 
             # Let's try to assume it's simple linear structure if AST fails?
             # But "1000(a+...)" is critical.
             raise ValueError(f"Syntax Error: {e}")

        # 3. Process AST
        result_terms = self._process_ast_node(tree.body)
        
        # 4. Format Output
        final_coeffs = {}
        const_val = 0.0
        
        for term in result_terms:
            # Term is (coeff, var_name)
            # var_name None means constant
            c, v = term
            if v is None:
                const_val += c
            else:
                final_coeffs[v] = final_coeffs.get(v, 0) + c
                
        def _fmt_coeff(c):
            """Format coefficient as decimal, never scientific notation."""
            if c == int(c):
                return f"{int(c):+d}"
            else:
                return f"{c:+.10f}".rstrip('0').rstrip('.')

        # Build string
        output_parts = []
        for var in sorted(final_coeffs.keys()):
            coeff = final_coeffs[var]
            if abs(coeff) < 1e-9: continue # Skip zero
            
            # Format - use decimal notation (never scientific notation like 1e+04)
            if coeff == 1:
                s = f"+{var}"
            elif coeff == -1:
                s = f"-{var}"
            else:
                s = f"{_fmt_coeff(coeff)}{var}"
            output_parts.append(s)
            
        if abs(const_val) > 1e-9:
            output_parts.append(_fmt_coeff(const_val))
            
        if not output_parts:
            return "0"
            
        return "".join(output_parts).lstrip('+')

    def _process_ast_node(self, node):
        """
        Returns a list of terms: [(coeff, params)...] where term is just (coeff, variable_name) 
        Linear expressions only.
        """
        if isinstance(node, ast.BinOp):
            left = self._process_ast_node(node.left)
            right = self._process_ast_node(node.right)
            
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                # Negate right
                radj = [(c * -1, v) for c, v in right]
                return left + radj
            elif isinstance(node.op, ast.Mult):
                # Distribute
                left_is_const = all(v is None for c, v in left)
                right_is_const = all(v is None for c, v in right)
                
                if left_is_const:
                    scalar = sum(c for c, v in left)
                    return [(c * scalar, v) for c, v in right]
                elif right_is_const:
                    scalar = sum(c for c, v in right)
                    return [(c * scalar, v) for c, v in left]
                else:
                    raise ValueError("Non-linear multiplication (Variable * Variable) is not supported.")
            elif isinstance(node.op, ast.Div):
                 # Division by constant allowed
                right_is_const = all(v is None for c, v in right)
                if not right_is_const:
                     raise ValueError("Division by variable not allowed")
                divisor = sum(c for c, v in right)
                if divisor == 0: raise ValueError("Division by zero")
                return [(c / divisor, v) for c, v in left]
                
        elif isinstance(node, ast.UnaryOp):
            operand = self._process_ast_node(node.operand)
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
            
        raise ValueError(f"Unsupported syntax in expression: {type(node)}")

    def parse(self):
        # 1. Parse Objective
        lower_obj = self.objective_str.lower()
        
        # If type not explicitly set, try to detect
        if not self.optimization_type:
            if lower_obj.startswith('max'):
                self.optimization_type = 'max'
            else:
                self.optimization_type = 'min'
        
        # Aggressively remove ANY occurrence of maximize/minimize/max/min to prevent phantom vars
        # This handles cases like "Minimize Minimize 2x..." where one is from UI, one from User
        clean_obj = lower_obj.replace('\u200b', '') # remove zero-width space
        clean_obj = clean_obj.replace('−', '-') # replace unicode minus with normal hyphen
        clean_obj = re.sub(r'(maximize|minimize|max|min)[:\s]*', '', clean_obj, flags=re.IGNORECASE).strip()
            
        self.objective_coeffs = self._parse_expression(clean_obj)
        
        # 2. Parse Constraints
        for i, c_str in enumerate(self.constraints_list):
            try:
                self._parse_single_constraint(c_str, i)
            except Exception as e:
                # Add context to error
                raise ValueError(f"Error in constraint line {i+1}: '{c_str}' -> {str(e)}")
        
        # 3. Sort variables for consistent matrix columns
        self.sorted_vars = sorted(list(self.variables))
        
        return self.build_matrices()

    def _parse_single_constraint(self, c_str, index):
        c_str = c_str.lower().replace('\u200b', '').replace('−', '-')
        # Detect operator
        if '<=' in c_str:
            op = '<='
            lhs, rhs = c_str.split('<=')
        elif '>=' in c_str:
            op = '>='
            lhs, rhs = c_str.split('>=')
        elif '=' in c_str: 
            op = '='
            lhs, rhs = c_str.split('=')
            if rhs.startswith('='): # Handle '=='
                rhs = rhs[1:]
        elif '≤' in c_str:
            op = '<='
            lhs, rhs = c_str.split('≤')
        elif '≥' in c_str:
            op = '>='
            lhs, rhs = c_str.split('≥')
        elif '<' in c_str:
            op = '<='
            lhs, rhs = c_str.split('<')
        elif '>' in c_str:
            op = '>='
            lhs, rhs = c_str.split('>')
        else:
            raise ValueError("Missing comparator (<=, >=, =, <, >)")
            
        lhs_coeffs = self._parse_expression(lhs)
        
        try:
            rhs_val = float(Fraction(rhs.strip()))
        except:
             raise ValueError(f"Invalid RHS value: {rhs}")

        # Store metadata for Detailed Reporting
        self.parsed_constraints.append({
            'lhs': lhs_coeffs,
            'op': op,
            'rhs': rhs_val,
            'original_text': c_str,
            'id': index,
            'type': 'ineq' if op != '=' else 'eq' 
        })

    def build_matrices(self):
        # Create C vector
        c = np.zeros(len(self.sorted_vars))
        for i, var in enumerate(self.sorted_vars):
            c[i] = self.objective_coeffs.get(var, 0)
            
        # Optimization direction: SciPy minimizes. If Max, flip C.
        if self.optimization_type == 'max':
             c_solver = -c
        else:
             c_solver = c
             
        # Create A_ub, b_ub, A_eq, b_eq
        A_ub = []
        b_ub = []
        A_eq = []
        b_eq = []
        
        # Track which solver row corresponds to which original constraint 
        # (for shadow price mapping)
        constraint_map = [] 
        
        ub_idx = 0
        eq_idx = 0
        
        for constr in self.parsed_constraints:
            row = np.zeros(len(self.sorted_vars))
            for i, var in enumerate(self.sorted_vars):
                row[i] = constr['lhs'].get(var, 0)
            
            op = constr['op']
            rhs = constr['rhs']
            
            mapped_info = {
                'original': constr,
                'solver_type': None,
                'solver_index': None
            }
            
            if op == '<=':
                A_ub.append(row)
                b_ub.append(rhs)
                mapped_info['solver_type'] = 'ub'
                mapped_info['solver_index'] = ub_idx
                ub_idx += 1
            elif op == '>=':
                # Convert ax >= b to -ax <= -b
                A_ub.append(-row)
                b_ub.append(-rhs)
                mapped_info['solver_type'] = 'ub'
                mapped_info['solver_index'] = ub_idx
                ub_idx += 1
            elif op == '=':
                A_eq.append(row)
                b_eq.append(rhs)
                mapped_info['solver_type'] = 'eq'
                mapped_info['solver_index'] = eq_idx
                eq_idx += 1
            
            constraint_map.append(mapped_info)
                
        return {
            'c': c_solver,
            'original_c': c, 
            'optimization_type': self.optimization_type,
            'variables': self.sorted_vars,
            'A_ub': np.array(A_ub) if A_ub else None,
            'b_ub': np.array(b_ub) if b_ub else None,
            'A_eq': np.array(A_eq) if A_eq else None,
            'b_eq': np.array(b_eq) if b_eq else None,
            'constraints_info': constraint_map
        }

if __name__ == "__main__":
    # Test
    parser = LPParser("Max 3x + 5y", ["x + y <= 10", "2x - y >= 5", "x = 4", "1/2x + y <= 3"])
    result = parser.parse()
    print("Vars:", result['variables'])
    print("C:", result['original_c'])
    print("A_ub:", result['A_ub'])
