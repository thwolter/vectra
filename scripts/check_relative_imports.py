#!/usr/bin/env python3
import re
import sys

ABS_IMPORT_RE = re.compile(r'^\s*from\s+app[\.\w]*\s+import\s+|^\s*import\s+app[\.\w]*')


def main():
    for filename in sys.argv[1:]:
        with open(filename, 'r') as f:
            for idx, line in enumerate(f, 1):
                if ABS_IMPORT_RE.match(line):
                    print(
                        f'{filename}:{idx}: '
                        f'Absolute import detected (use relative import): {line.strip()}'
                    )
                    return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
