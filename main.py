"""CLI entrypoint — run a single task through the orchestrator."""
import sys
from config import load_config

load_config()

from orchestrator import run

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python main.py "<task>"')
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    print(f"\nTask: {task}\n")
    print("─" * 60)
    result, _history, agents = run(task)
    print(result)
    print("─" * 60)
    print(f"Handled by: {', '.join(agents)}")
