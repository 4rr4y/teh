import sys
from _lib import write, run

PROMPT = ("Add a --top N option to wordcount.py: after its summary line, print the N most common words, one per line "
          "as 'word count', most common first, ties in alphabetical order. Without --top the output must not change.")
KIND, SIZE, WEB = "dev", "short", False

CODE = '''"""Counts the words in a text file: python3 wordcount.py FILE"""
import argparse
import collections
import re


def count_words(text):
    return collections.Counter(re.findall(r"[a-z']+", text.lower()))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Count the words in a text file.")
    parser.add_argument("file")
    args = parser.parse_args(argv)
    with open(args.file, encoding="utf-8") as f:
        counts = count_words(f.read())
    print(f"{sum(counts.values())} words, {len(counts)} different")


if __name__ == "__main__":
    main()
'''
SAMPLE = "the cat and the hat. The bat and a cat! zebra apple apple\n"

def setup(d):
    write(d, "wordcount.py", CODE)
    write(d, "sample.txt", "It was the best of times, it was the worst of times.\n")

def expected(top=None):
    import collections, re
    counts = collections.Counter(re.findall(r"[a-z']+", SAMPLE.lower()))
    lines = [f"{sum(counts.values())} words, {len(counts)} different"]
    if top:
        lines += [f"{w} {n}" for w, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:top]]
    return "\n".join(lines)

def check(d, answer):
    write(d, ".check/in.txt", SAMPLE)
    for top in (None, 3, 1, 20):
        args = ["--top", str(top)] if top else []
        code, out = run([sys.executable, "-B", "wordcount.py", ".check/in.txt", *args], d)
        if code != 0 or out.strip() != expected(top):
            return False, f"wordcount.py {' '.join(args)}: got {out.strip()!r}, expected {expected(top)!r}"
    code, out = run([sys.executable, "-B", "wordcount.py", "--top", "2", ".check/in.txt"], d)  # option first
    return code == 0 and out.strip() == expected(2), f"--top before the file: {out.strip()!r}"
