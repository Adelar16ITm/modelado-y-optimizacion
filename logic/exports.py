import pandas as pd
import io

def generate_csv(vertices_data, solution_data, constraints_data):
    """
    Generates a CSV string containing multiple tables:
    1. Optimal Solution Summary
    2. Vertices details
    3. Constraints summary
    """
    
    # Create sections
    csv_buffer = io.StringIO()
    
    # 1. Summary
    csv_buffer.write("--- OPTIMAL SOLUTION SUMMARY ---\n")
    if solution_data:
        for k, v in solution_data.items():
            csv_buffer.write(f"{k},{v}\n")
    else:
        csv_buffer.write("No solution found.\n")
    
    csv_buffer.write("\n")
    
    # 2. Vertices
    csv_buffer.write("--- VERTICES ANALYSIS (2D) ---\n")
    if vertices_data:
        df_v = pd.DataFrame(vertices_data)
        df_v.to_csv(csv_buffer, index=False)
    else:
        csv_buffer.write("No vertices available.\n")
        
    csv_buffer.write("\n")
    
    # 3. Constraints
    csv_buffer.write("--- CONSTRAINTS ANALYSIS ---\n")
    if constraints_data:
        df_c = pd.DataFrame(constraints_data)
        df_c.to_csv(csv_buffer, index=False)
    else:
        csv_buffer.write("No constraints.\n")
        
    return csv_buffer.getvalue().encode('utf-8')

def generate_png(fig):
    """
    Generates PNG bytes from Plotly figure using Kaleido.
    """
    # Force static size for download if needed, or rely on fig layout
    img_bytes = fig.to_image(format="png", width=1200, height=800, scale=2)
    return img_bytes
