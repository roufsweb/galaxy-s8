import sys
import os
import re

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DOCS = ['HISTORY.md', 'FINDINGS.md', 'GEMINI.md', 'SUMMARY.md']

def search_files(keyword):
    print(f"\n==========================================")
    print(f" SEARCHING KNOWLEDGE BASE FOR: '{keyword}'")
    print(f"==========================================\n")
    found_any = False
    kw_re = re.compile(re.escape(keyword), re.IGNORECASE)

    for doc in DOCS:
        path = os.path.join(ROOT_DIR, doc)
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        matches = []
        for i, line in enumerate(lines):
            if kw_re.search(line):
                # Grab a small context block
                start = max(0, i - 1)
                end = min(len(lines), i + 3)
                context = lines[start:end]
                matches.append((i + 1, context))

        if matches:
            found_any = True
            print(f"--- Matches in {doc} ({len(matches)} occurrences) ---")
            for line_no, ctx in matches[:5]:
                print(f"  [Line {line_no}]:")
                for c in ctx:
                    print(f"    | {c.rstrip()}")
                print()
            if len(matches) > 5:
                print(f"  ... and {len(matches) - 5} more occurrences in {doc}.\n")

    if not found_any:
        print(f"No matches found for '{keyword}'.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python search_history.py <keyword>")
        sys.exit(1)
    search_files(" ".join(sys.argv[1:]))

