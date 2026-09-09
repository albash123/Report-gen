"""Usage: python generate_report.py workbook.xlsx [--output report.html]."""

import argparse
import sys
from report_generator.logging_setup import configure_logging
from report_generator.models import WorkbookError
from report_generator.renderer import generate_report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a portable weekly HTML report from Excel."
    )
    parser.add_argument("workbook", help="Path to an .xlsx weekly report")
    parser.add_argument("--output", "-o", help="Optional destination .html file")
    args = parser.parse_args(argv)
    try:
        logger = configure_logging()
        output, context = generate_report(args.workbook, args.output)
        logger.info(
            "Generated %s from %s; %s warnings", output, args.workbook, len(context["warnings"])
        )
        print(f"Report generated: {output}")
        for warning in context["warnings"]:
            logger.info("Source diagnostic: %s", warning)
        return 0
    except WorkbookError as exc:
        logging_error(exc)
        print(f"Could not generate report: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        logging_error(exc)
        print(
            "Could not generate report. Check that the workbook is readable and the output folder is writable. Technical details are in logs/report_generator.log.",
            file=sys.stderr,
        )
        return 1


def logging_error(exc):
    try:
        configure_logging().exception("Report generation failed: %s", exc)
    except OSError:
        pass


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
