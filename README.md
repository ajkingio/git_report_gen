# Git Report Generator

## Summary

This is a simple report generator for Git repositories. Right now it only generates a commit report but I may add more report options in the future.

## Usage
```
Git Commit Report Generator

USAGE:
    ./git_report_gen.py <repo_path> [time_range] [output_dir]
    ./git_report_gen.py -h | --help

ARGUMENTS:
    repo_path       Path to the Git repository (required)
    time_range      Time period for the report (optional, default: 1.week)
    output_dir      Directory where the report will be saved (optional, default: current directory)

TIME RANGE OPTIONS:
    1.week          Last 7 days
    2.weeks         Last 14 days
    1.month         Last 30 days
    2.months        Last 60 days
    3.months        Last 90 days
    6.months        Last 180 days
    1.year          Last 365 days

EXAMPLES:
    # Generate report for last week, save to current directory
    ./git_report_gen.py /path/to/repo

    # Generate report for last 2 weeks, save to current directory
    ./git_report_gen.py /path/to/repo 2.weeks

    # Generate report for last month, save to /tmp
    ./git_report_gen.py /path/to/repo 1.month /tmp

    # Generate report for last 3 months, save to ~/reports
    ./git_report_gen.py /path/to/repo 3.months ~/reports

OUTPUT:
    The report will be saved as a markdown file with the following format:
    YYYYMMDD_<repo_name>_<time_range>_commit_report.md

    The report includes:
    - File change statistics (added, modified, deleted)
    - Commit summary by author
    - Detailed commits by author
    - Complete file diffs for all changes
  ```
