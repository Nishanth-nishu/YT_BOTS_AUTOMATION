"""python -m animeforge.registry [--role voice]"""
import sys

from animeforge.registry import problems, table

role = sys.argv[sys.argv.index("--role") + 1] if "--role" in sys.argv else None
bad = problems()
print(table(role))
if bad:
    print("\nregistry problems:\n  " + "\n  ".join(bad), file=sys.stderr)
sys.exit(1 if bad else 0)
