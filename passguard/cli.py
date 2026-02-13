"""PassGuard command-line interface.

Usage examples:
    python -m passguard check mypassword
    python -m passguard check -f passwords.txt --strength
    python -m passguard generate -n 20 -c 5
"""

import argparse
import sys

from passguard import check_breach, check_email_breach, score_strength, generate_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="passguard",
        description="Check password security against known data breaches.",
    )
    sub = parser.add_subparsers(dest="command")

    # ── check ──────────────────────────────────────────────────────────
    check_p = sub.add_parser(
        "check", help="Check passwords against breach databases",
    )
    check_p.add_argument("passwords", nargs="*", help="Passwords to check")
    check_p.add_argument(
        "-f", "--file",
        help="Read passwords from a file (one per line)",
    )
    check_p.add_argument(
        "-s", "--strength",
        action="store_true",
        help="Include strength analysis in output",
    )

    # ── generate ───────────────────────────────────────────────────────
    gen_p = sub.add_parser("generate", help="Generate secure passwords")
    gen_p.add_argument(
        "-n", "--length", type=int, default=12,
        help="Password length (default: 12)",
    )
    gen_p.add_argument("--no-uppercase", action="store_true")
    gen_p.add_argument("--no-digits", action="store_true")
    gen_p.add_argument("--no-symbols", action="store_true")
    gen_p.add_argument(
        "-c", "--count", type=int, default=1,
        help="Number of passwords to generate (default: 1)",
    )

    # ── email ─────────────────────────────────────────────────────────
    email_p = sub.add_parser(
        "email", help="Check emails against breach databases",
    )
    email_p.add_argument("emails", nargs="+", help="Email addresses to check")

    args = parser.parse_args(argv)

    if args.command == "check":
        return _cmd_check(args)
    if args.command == "generate":
        return _cmd_generate(args)
    if args.command == "email":
        return _cmd_email(args)

    parser.print_help()
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    passwords = list(args.passwords)

    if args.file:
        with open(args.file) as f:
            passwords.extend(line.strip() for line in f if line.strip())

    if not passwords:
        print("Error: provide passwords as arguments or via --file", file=sys.stderr)
        return 1

    breached = False
    for pwd in passwords:
        count = check_breach(pwd)
        if count:
            print(f"  BREACHED  '{pwd}' -- found {count:,} times")
            breached = True
        else:
            print(f"  Safe      '{pwd}' -- not found in any known breaches")

        if args.strength:
            report = score_strength(pwd)
            filled = report["score"] + 1
            bar = "#" * filled + "-" * (5 - filled)
            print(f"            Strength: [{bar}] {report['label']} ({report['entropy']} bits)")
            for w in report["warnings"]:
                print(f"            ! {w}")

    return 1 if breached else 0


def _cmd_email(args: argparse.Namespace) -> int:
    any_exposed = False
    for email in args.emails:
        result = check_email_breach(email)

        if result["errors"] and not result["sources_checked"]:
            print(f"  ERROR   '{email}' -- {'; '.join(result['errors'])}")
            continue

        if result["exposed"]:
            any_exposed = True
            print(f"  EXPOSED '{email}' -- found in {len(result['breaches'])} breach(es)")
            for b in result["breaches"]:
                date_str = f" ({b['date']})" if b["date"] else ""
                print(f"            - {b['name']}{date_str}  [{b['source']}]")
        else:
            print(f"  Safe    '{email}' -- not found in any known breaches")

        if result["errors"]:
            for err in result["errors"]:
                print(f"            ! {err}")

        if result["sources_checked"]:
            print(f"            Sources: {', '.join(result['sources_checked'])}")

    return 1 if any_exposed else 0


def _cmd_generate(args: argparse.Namespace) -> int:
    for _ in range(args.count):
        pwd = generate_password(
            args.length,
            uppercase=not args.no_uppercase,
            digits=not args.no_digits,
            symbols=not args.no_symbols,
        )
        report = score_strength(pwd)
        print(f"  {pwd}  ({report['label']}, {report['entropy']} bits)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
