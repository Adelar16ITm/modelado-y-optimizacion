class TemplateManager:
    @staticmethod
    def get_templates():
        return {
            "Select Template...": {
                "objective": "",
                "constraints": "",
                "description": ""
            },
            "Manufactura (2D Classic)": {
                "objective": "Maximize 8x + 10y",
                "constraints": "x + y <= 1100\n0.5x + 0.5y <= 600\n0.667x + y <= 800\n0.25x + 0.5y <= 375\nx >= 0\ny >= 0",
                "description": "Standard resource allocation problem."
            },
            "Diet Problem (Minimization)": {
                "objective": "Minimize 0.6x + 0.4y",
                "constraints": "200x + 150y >= 1000\n10x + 5y >= 40\nx >= 0\ny >= 0",
                "description": "Minimize cost while satisfying nutritional requirements."
            },
            "Investment (Mixed Constraints)": {
                "objective": "Maximize 0.08x + 0.12y",
                "constraints": "x + y <= 10000\nx <= 6000\ny <= 6000\nx - y >= 0\nx >= 0\ny >= 0",
                "description": "Portfolio selection with risk limits."
            }
        }
