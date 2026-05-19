import pulp

class IPSolver:
    def __init__(self, objective_str, constraints_list, maximize=True, integer_vars=None, binary_vars=None):
        self.objective_str = objective_str
        self.constraints_list = constraints_list
        self.maximize = maximize
        self.integer_vars = integer_vars if integer_vars else []
        self.binary_vars = binary_vars if binary_vars else []
        self.prob = None
        self.vars_dict = {}

    def solve(self):
        # 1. Initialize Problem
        sense = pulp.LpMaximize if self.maximize else pulp.LpMinimize
        self.prob = pulp.LpProblem("IP_Problem", sense)
        
        # 2. Extract Variables from strings (simple parsing reuse or regex here)
        # We need to know all variables first to create PuLP objects
        # For robustness, we'll scan the strings
        all_vars = set()
        import re
        tokens = re.findall(r'[a-zA-Z_]\w*', self.objective_str + " ".join(self.constraints_list))
        for t in tokens:
            if t not in ["Max", "Min", "Maximize", "Minimize", "Subject", "to"]:
                all_vars.add(t)
                
        # Create PuLP Variables
        for v in all_vars:
            cat = pulp.LpContinuous
            low_bound = 0 # Default non-negative
            
            if v in self.binary_vars:
                cat = pulp.LpBinary
                low_bound = 0
            elif v in self.integer_vars:
                cat = pulp.LpInteger
                low_bound = 0
                
            self.vars_dict[v] = pulp.LpVariable(v, lowBound=low_bound, cat=cat)
            
        # 3. Add Objective
        # Naive parsing: "3x + 5y"
        # We can use eval() with a safe dictionary if strings are clean, 
        # or reuse our LPParser coeff logic.
        # Let's use eval for speed in this demo, but strictly controlled
        # OR better: reuse LPParser to get coefficients and build expression
        
        # Fallback simplistic eval context
        eval_context = self.vars_dict.copy()
        try:
            # Handle implicit multiplication 3x -> 3*x ? No, Python doesn't do that.
            # User input usually "3x". We need to pre-process "3x" -> "3*x"
            # This is complex. Let's rely on our LPParser if possible or custom regex replacement.
            
            # Simple approach: Require explicit "*" or fix it
            # Re-implementing a quick parser specifically for PuLP building
            
             # Temporarily assume standard "3*x + 5*y" or force user? 
             # No, users type "3x".
             
             # HACK: Use our existing LPParser to get coeffs, then build PuLP expression
             from modules.lp_parser import LPParser
             full_obj = f"Max {self.objective_str}" if self.maximize else f"Min {self.objective_str}"
             parser = LPParser(full_obj, self.constraints_list)
             data = parser.parse() # efficient
             
             # Build Objective
             obj_expr = 0
             for i, v_name in enumerate(data['variables']):
                 c_val = data['original_c'][i]
                 obj_expr += c_val * self.vars_dict[v_name]
                 
             self.prob += obj_expr
             
             # Build Constraints
             for constr in data['constraints_info']:
                 lhs_expr = 0
                 for v_name, coeff in constr['lhs'].items():
                     lhs_expr += coeff * self.vars_dict[v_name]
                     
                 if constr['op'] == '<=':
                     self.prob += (lhs_expr <= constr['rhs'])
                 elif constr['op'] == '>=':
                     self.prob += (lhs_expr >= constr['rhs'])
                 elif constr['op'] == '=':
                     self.prob += (lhs_expr == constr['rhs'])
                     
             # Solve
             status = self.prob.solve(pulp.PULP_CBC_CMD(msg=False))
             
             # Result
             return {
                 "status": pulp.LpStatus[status],
                 "objective": pulp.value(self.prob.objective),
                 "variables": {v: pulp.value(var) for v, var in self.vars_dict.items()},
                 "bnb_tree": "Simplified Tree: Root -> Integer Solution Found" # Placeholder for B&B viz
             }
             
        except Exception as e:
            return {"status": "Error", "message": f"IP Parsing/Solver Error: {str(e)}"}
