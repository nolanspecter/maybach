import subprocess
import tempfile
import os
from langchain_core.tools import tool


@tool
def run_python(code: str) -> str:
    """Execute Python code in a subprocess and return stdout/stderr."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if err:
            return f"stdout:\n{out}\n\nstderr:\n{err}" if out else f"stderr:\n{err}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: code execution timed out (30s)"
    except Exception as e:
        return f"Error: {e}"
    finally:
        os.unlink(path)


@tool
def run_bash(command: str) -> str:
    """Run a shell command and return output. Single commands only, no pipes to sensitive ops."""
    try:
        result = subprocess.run(
            command,
            shell=True,
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
