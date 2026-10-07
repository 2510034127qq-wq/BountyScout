import sys
from scanner import scan_repository, format_report


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <repository> [max_issues]")
        sys.exit(1)

    repo = sys.argv[1]
    max_issues = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    results = scan_repository(repo, max_issues)
    report = format_report(results)
    print(report)


if __name__ == "__main__":
    main()
