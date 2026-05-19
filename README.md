# OR Workbench Pro

A professional-grade Operations Research (OR) web application built with Python and Streamlit.
Designed for students and professionals to solve and analyze:
- Linear Programming (LP) with Graphical Method & Sensitivity
- Simplex Algorithm (Step-by-Step Tutor)
- Transportation & Assignment Problems
- Network Models (Shortest Path, MST, Max Flow)
- Integer Programming (IP/MILP)
- Dynamic Programming (DP)

## Installation (Windows)

1.  **Install Python 3.9+** (if not already installed).
2.  **Install Dependencies**:
    Open a terminal (PowerShell or Command Prompt) in this folder and run:
    ```bash
    pip install -r requirements.txt
    ```

## Running the App

Run the following command in your terminal:
```bash
streamlit run app.py
```
A browser window should open automatically at `http://localhost:8501`.

## Features
- **Exam Mode**: Clean, distraction-free interface.
- **Robust Parser**: Accepts natural equations (`3x + 2y <= 10`, `1/2x...`).
- **Templates**: Pre-loaded cases for quick testing (Manufactura, Diet, etc.).
- **Downloads**: Export Solutions (CSV) and Graphs (PNG, via interactive plot).

## Troubleshooting
- If `kaleido` fails to install, the static image export might be limited, but the interactive app will still work.
- For Integer Programming to work efficiently, `pip install pulp` (included in requirements) uses the default CBC solver.
