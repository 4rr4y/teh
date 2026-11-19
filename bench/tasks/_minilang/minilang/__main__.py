"""python3 -m minilang FILE: runs a program. python3 -m minilang --format FILE: prints it formatted."""
import sys

from . import format_source, run
from .errors import LangError


def main(argv):
    if len(argv) == 2 and argv[0] == "--format":
        source, fmt = open(argv[1], encoding="utf-8").read(), True
    elif len(argv) == 1:
        source, fmt = open(argv[0], encoding="utf-8").read(), False
    else:
        print("usage: python3 -m minilang [--format] FILE", file=sys.stderr)
        return 2
    try:
        if fmt:
            sys.stdout.write(format_source(source))
        else:
            run(source)
    except LangError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
