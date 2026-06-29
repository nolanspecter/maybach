import subprocess
import tempfile
import os
from core.tools import tool


@tool
def run_python(code: str) -> str:
    """Execute Python code in a subprocess and return stdout/stderr."""
    # Write to a temp file so the subprocess gets a real file path.
    # delete=False because the file must exist when subprocess.run() is called.
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=30,  # prevent runaway loops from hanging the server
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        # Return both streams if both have content so the LLM sees the full picture
        if err:
            return f"stdout:\n{out}\n\nstderr:\n{err}" if out else f"stderr:\n{err}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: code execution timed out (30s)"
    except Exception as e:
        return f"Error: {e}"
    finally:
        os.unlink(path)  # always clean up even if execution failed


@tool
def run_bash(command: str) -> str:
    """Run a shell command and return output. Single commands only, no pipes to sensitive ops."""
    try:
        result = subprocess.run(
            command,
            shell=True,      # needed to support env vars and builtins
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if err:
            return f"stdout:\n{out}\n\nstderr:\n{err}" if out else f"stderr:\n{err}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out (15s)"
    except Exception as e:
        return f"Error: {e}"
