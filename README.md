# Git Report Generator

## Summary

A comprehensive report generator for Git repositories that generates both detailed commit reports and high-level GitHub activity summaries. Track code changes, commits, issues, and pull requests all in one place.

## Features

- **Detailed Commit Reports**: Track file changes, commits by author, and complete diffs
- **GitHub Activity Summaries**: Monitor issues and pull requests (created, updated, merged, closed)
- **Flexible Time Ranges**: Generate reports for any time period from 1 week to 1 year
- **Selective Report Generation**: Generate commit reports, GitHub summaries, or both

## Requirements

- Python 3.6+
- Git (for commit reports)
- [GitHub CLI (`gh`)](https://cli.github.com/) (for GitHub activity summaries)

## Installation

1. Clone or download this repository
2. Make the script executable:
   ```bash
   chmod +x git_report_gen.py
   ```
3. (Optional) Install GitHub CLI for GitHub activity summaries:
   ```bash
   # macOS
   brew install gh
   
   # Linux
   See https://github.com/cli/cli/blob/trunk/docs/install_linux.md
   
   # Windows
   See https://github.com/cli/cli#windows
   ```

## Usage

```
Git Report Generator

USAGE:
    ./git_report_gen.py <repo_path> [options]
    ./git_report_gen.py -h | --help

ARGUMENTS:
    repo_path       Path to the Git repository (required)

OPTIONS:
    --time-range RANGE      Time period for the report (default: 1.week)
    --output-dir DIR        Directory where reports will be saved (default: current directory)
    --report-type TYPE      Type of report to generate: all, commits, github (default: all)
    -h, --help              Show this help message

TIME RANGE OPTIONS:
    1.week          Last 7 days
    2.weeks         Last 14 days
    1.month         Last 30 days
    2.months        Last 60 days
    3.months        Last 90 days
    6.months        Last 180 days
    1.year          Last 365 days

REPORT TYPES:
    all             Generate both commit report and GitHub summary (default)
    commits         Generate only the detailed commit report
    github          Generate only the GitHub activity summary (requires GitHub CLI)

EXAMPLES:
    # Generate both reports for last week, save to current directory
    ./git_report_gen.py /path/to/repo

    # Generate both reports for last 2 weeks
    ./git_report_gen.py /path/to/repo --time-range 2.weeks

    # Generate only commit report for last month, save to /tmp
    ./git_report_gen.py /path/to/repo --time-range 1.month --output-dir /tmp --report-type commits

    # Generate only GitHub summary for last 3 months, save to ~/reports
    ./git_report_gen.py /path/to/repo --time-range 3.months --output-dir ~/reports --report-type github

OUTPUT:
    Reports will be saved as markdown files with the following formats:
    - Commit report: YYYYMMDD_<repo_name>_<time_range>_commit_report.md
    - GitHub summary: YYYYMMDD_<repo_name>_<time_range>_github_summary.md

    Commit report includes:
    - File change statistics (added, modified, deleted)
    - Commit summary by author
    - Detailed commits by author
    - Complete file diffs for all changes

    GitHub summary includes (requires GitHub CLI 'gh'):
    - Issues created, updated, and closed
    - Pull requests created, updated, merged, and closed
    - Detailed lists of all issues and PRs
```

## Report Examples

### Commit Report

The commit report includes:
- Summary of files added, modified, and deleted
- Commit counts by author
- Detailed commit history grouped by author
- Complete file diffs for all changes in the period

### GitHub Summary

The GitHub activity summary includes:
- Count of issues created, updated, and closed
- Count of PRs created, updated, merged, and closed
- Detailed lists of all issues and PRs with titles and authors

## Troubleshooting

### GitHub CLI Not Found

If you see an error about `gh` not being found:
1. Install the GitHub CLI from https://cli.github.com/
2. Authenticate with GitHub: `gh auth login`
3. Ensure `gh` is in your PATH

Alternatively, use `--report-type commits` to generate only the commit report which doesn't require GitHub CLI.

### Permission Errors

If you encounter permission errors when writing reports:
1. Check that the output directory exists and is writable
2. Try specifying a different output directory with `--output-dir`
