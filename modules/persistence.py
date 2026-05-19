"""
Persistence Manager for OR Workbench Pro
Handles saving and loading user sessions to JSON files.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Storage directory (relative to app root)
SESSIONS_DIR = Path(__file__).parent.parent / "saved_sessions"


def ensure_dir():
    """Create sessions directory if it doesn't exist."""
    SESSIONS_DIR.mkdir(exist_ok=True)


def get_session_path(name: str) -> Path:
    """Get the full path for a session file."""
    # Sanitize filename
    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
    return SESSIONS_DIR / f"{safe_name}.json"


def save_session(name: str, module: str, data: dict) -> bool:
    """
    Save a session to disk.
    
    Args:
        name: User-friendly session name
        module: Which module this belongs to (e.g., "Linear Programming")
        data: Dict containing the session data
        
    Returns:
        True if successful, False otherwise
    """
    ensure_dir()
    
    session = {
        "name": name,
        "module": module,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    try:
        with open(get_session_path(name), 'w', encoding='utf-8') as f:
            json.dump(session, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving session: {e}")
        return False


def load_session(name: str) -> Optional[dict]:
    """
    Load a session from disk.
    
    Args:
        name: Session name to load
        
    Returns:
        Session dict if found, None otherwise
    """
    path = get_session_path(name)
    if not path.exists():
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading session: {e}")
        return None


def list_sessions(module: Optional[str] = None) -> list[dict]:
    """
    List all saved sessions.
    
    Args:
        module: Optional filter by module name
        
    Returns:
        List of session info dicts with name, module, and timestamp
    """
    ensure_dir()
    sessions = []
    
    for file in SESSIONS_DIR.glob("*.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if module is None or data.get("module") == module:
                    sessions.append({
                        "name": data.get("name", file.stem),
                        "module": data.get("module", "Unknown"),
                        "timestamp": data.get("timestamp", "")
                    })
        except:
            continue
    
    # Sort by timestamp descending (newest first)
    sessions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return sessions


def delete_session(name: str) -> bool:
    """Delete a saved session."""
    path = get_session_path(name)
    try:
        if path.exists():
            path.unlink()
            return True
    except Exception as e:
        print(f"Error deleting session: {e}")
    return False


def save_last_session(module: str, data: dict):
    """Auto-save the last session for quick restore."""
    save_session(f"_autosave_{module}", module, data)


def load_last_session(module: str) -> Optional[dict]:
    """Load the auto-saved last session."""
    return load_session(f"_autosave_{module}")
