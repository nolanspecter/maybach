"""CLI entrypoint — run a task through the orchestrator."""
import sys
from dotenv import load_dotenv

load_dotenv()

from orchestrator import run

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py \"<task>\"")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    print(f"\nTask: {task}\n")
    print("─" * 60)
    result = run(task)
    print(result)
