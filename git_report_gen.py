#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def run_git_command(repo_path, *args):
    """Run a git command in the specified repository."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path] + list(args),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}", file=sys.stderr)
        return None


def run_gh_command(repo_path, *args, silent=False):
    """Run a GitHub CLI command in the specified repository."""
    try:
        result = subprocess.run(
            ["gh"] + list(args),
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_path,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Silently return None for expected failures (auth issues, rate limits, etc.)
        if silent:
            return None
        print(f"Error running gh command: {e}", file=sys.stderr)
        return None
    except FileNotFoundError:
        if not silent:
            print(
                "Error: GitHub CLI (gh) is not installed or not in PATH.",
                file=sys.stderr,
            )
            print("Install it from: https://cli.github.com/", file=sys.stderr)
        return None


def is_github_repo(repo_path):
    """Check if the repository is hosted on GitHub."""
    try:
        remote_url = run_git_command(repo_path, "config", "--get", "remote.origin.url")
        if not remote_url:
            return False
        return "github.com" in remote_url
    except Exception:
        return False


def get_github_repo_url(repo_path):
    """Get the GitHub repository URL from git remote."""
    try:
        # Get the remote URL
        remote_url = run_git_command(repo_path, "config", "--get", "remote.origin.url")
        if not remote_url:
            return None

        # Convert SSH URLs to HTTPS format
        # SSH format: git@github.com:owner/repo.git
        # HTTPS format: https://github.com/owner/repo.git or https://github.com/owner/repo
        if remote_url.startswith("git@github.com:"):
            # Convert git@github.com:owner/repo.git to https://github.com/owner/repo
            repo_part = remote_url.replace("git@github.com:", "")
            if repo_part.endswith(".git"):
                repo_part = repo_part[:-4]  # Remove .git suffix
            return f"https://github.com/{repo_part}"
        elif "github.com" in remote_url:
            # Already HTTPS, just remove .git if present
            if remote_url.endswith(".git"):
                return remote_url[:-4]  # Remove .git suffix
            return remote_url

        return None
    except Exception:
        return None


def get_commit_counts(repo_path, since):
    """Get commit counts per author for the specified time period."""
    output = run_git_command(repo_path, "shortlog", "-sne", f"--since={since}")
    if not output:
        return []

    counts = []
    for line in output.split("\n"):
        if line.strip():
            parts = line.strip().split("\t", 1)
            count = int(parts[0].strip())
            author_email = parts[1].strip() if len(parts) > 1 else "Unknown"
            counts.append((count, author_email))

    return counts


def get_detailed_commits(repo_path, since):
    """Get detailed commit information grouped by author."""
    # Get commit hashes and basic info
    log_output = run_git_command(
        repo_path, "log", f"--since={since}", "--pretty=format:%H|%an|%ae|%ar|%s"
    )

    if not log_output:
        return {}

    commits_by_author = defaultdict(list)

    for line in log_output.split("\n"):
        if not line.strip():
            continue

        parts = line.split("|", 4)
        if len(parts) < 5:
            continue

        commit_hash, author_name, author_email, relative_date, subject = parts
        author_key = f"{author_name} <{author_email}>"

        # Get files changed in this commit
        stat_output = run_git_command(
            repo_path, "show", "--stat", "--format=", commit_hash
        )

        files_changed = []
        if stat_output:
            for stat_line in stat_output.split("\n"):
                if stat_line.strip() and "|" in stat_line:
                    # Parse file change stats
                    file_info = stat_line.strip()
                    files_changed.append(file_info)

        # Get the diff for this commit
        diff_output = run_git_command(
            repo_path, "show", "--format=", "--stat", commit_hash
        )

        commits_by_author[author_key].append(
            {
                "hash": commit_hash[:7],
                "subject": subject,
                "date": relative_date,
                "files": files_changed,
                "diff_summary": diff_output,
            }
        )

    return commits_by_author


def get_file_change_stats(repo_path, since):
    """Get counts of unique files added, modified, and deleted in the specified time period."""
    # Get all commits from the specified time period
    log_output = run_git_command(
        repo_path, "log", f"--since={since}", "--pretty=format:%H"
    )

    if not log_output:
        return {"added": 0, "modified": 0, "deleted": 0}

    commit_hashes = log_output.split("\n")

    # Track unique files and their most recent status
    # We'll use sets to track files that were added or deleted
    # and track the first status we see for each file
    added_files = set()
    deleted_files = set()
    modified_files = set()

    for commit_hash in commit_hashes:
        if not commit_hash.strip():
            continue

        # Get the status of files changed in this commit
        diff_output = run_git_command(
            repo_path, "diff-tree", "--no-commit-id", "--name-status", "-r", commit_hash
        )

        if not diff_output:
            continue

        for line in diff_output.split("\n"):
            if not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            status = parts[0]
            file_path = parts[1]

            # Track additions - a file was created in this period
            if status.startswith("A"):
                # If we haven't seen this file as deleted, mark it as added
                if file_path not in deleted_files:
                    added_files.add(file_path)
                    # Remove from modified if it was there (new file takes precedence)
                    modified_files.discard(file_path)

            # Track deletions
            elif status.startswith("D"):
                # If this file was added in this period, remove it from added
                # (file was added then deleted = net zero)
                if file_path in added_files:
                    added_files.discard(file_path)
                else:
                    deleted_files.add(file_path)
                # Remove from modified since it's now deleted
                modified_files.discard(file_path)

            # Track modifications - only if not already tracked as added or deleted
            elif status.startswith("M"):
                if file_path not in added_files and file_path not in deleted_files:
                    modified_files.add(file_path)

    return {
        "added": len(added_files),
        "modified": len(modified_files),
        "deleted": len(deleted_files),
    }


def calculate_since_date(since):
    """Convert git time range format to ISO date."""
    from datetime import timedelta

    # Parse the time range format (e.g., "1.week", "2.months")
    parts = since.split(".")
    if len(parts) != 2:
        # If not in expected format, default to 7 days ago
        return (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        num = int(parts[0])
        unit = parts[1].lower()

        # Calculate days based on unit
        if unit in ["week", "weeks"]:
            days = num * 7
        elif unit in ["month", "months"]:
            days = num * 30
        elif unit in ["year", "years"]:
            days = num * 365
        elif unit in ["day", "days"]:
            days = num
        else:
            days = 7  # Default to 1 week

        # Calculate the date
        target_date = datetime.now() - timedelta(days=days)
        return target_date.strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        # If parsing fails, default to 7 days ago
        return (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")


def get_github_issues_stats(repo_path, since):
    """Get statistics about GitHub issues for the specified time period."""
    # Convert since format to ISO date
    since_date = calculate_since_date(since)

    stats = {"created": [], "updated": [], "closed": []}

    # Get issues created in the period
    created_output = run_gh_command(
        repo_path,
        "issue",
        "list",
        "--search",
        f"created:>={since_date}",
        "--json",
        "number,title,author,createdAt,state",
        "--limit",
        "1000",
        silent=True,
    )

    if created_output:
        try:
            stats["created"] = json.loads(created_output)
        except json.JSONDecodeError:
            pass

    # Get issues updated in the period
    updated_output = run_gh_command(
        repo_path,
        "issue",
        "list",
        "--search",
        f"updated:>={since_date}",
        "--json",
        "number,title,author,updatedAt,state",
        "--limit",
        "1000",
        silent=True,
    )

    if updated_output:
        try:
            stats["updated"] = json.loads(updated_output)
        except json.JSONDecodeError:
            pass

    # Get issues closed in the period
    closed_output = run_gh_command(
        repo_path,
        "issue",
        "list",
        "--search",
        f"closed:>={since_date}",
        "--state",
        "closed",
        "--json",
        "number,title,author,closedAt,state",
        "--limit",
        "1000",
        silent=True,
    )

    if closed_output:
        try:
            stats["closed"] = json.loads(closed_output)
        except json.JSONDecodeError:
            pass

    return stats


def get_github_pr_stats(repo_path, since):
    """Get statistics about GitHub pull requests for the specified time period."""
    # Convert since format to ISO date
    since_date = calculate_since_date(since)

    stats = {"created": [], "updated": [], "merged": [], "closed": []}

    # Get PRs created in the period
    created_output = run_gh_command(
        repo_path,
        "pr",
        "list",
        "--search",
        f"created:>={since_date}",
        "--json",
        "number,title,author,createdAt,state",
        "--limit",
        "1000",
        silent=True,
    )

    if created_output:
        try:
            stats["created"] = json.loads(created_output)
        except json.JSONDecodeError:
            pass

    # Get PRs updated in the period
    updated_output = run_gh_command(
        repo_path,
        "pr",
        "list",
        "--search",
        f"updated:>={since_date}",
        "--json",
        "number,title,author,updatedAt,state",
        "--limit",
        "1000",
        silent=True,
    )

    if updated_output:
        try:
            stats["updated"] = json.loads(updated_output)
        except json.JSONDecodeError:
            pass

    # Get PRs merged in the period
    merged_output = run_gh_command(
        repo_path,
        "pr",
        "list",
        "--search",
        f"merged:>={since_date}",
        "--state",
        "merged",
        "--json",
        "number,title,author,mergedAt",
        "--limit",
        "1000",
        silent=True,
    )

    if merged_output:
        try:
            stats["merged"] = json.loads(merged_output)
        except json.JSONDecodeError:
            pass

    # Get PRs closed (but not merged) in the period
    closed_output = run_gh_command(
        repo_path,
        "pr",
        "list",
        "--search",
        f"closed:>={since_date} is:unmerged",
        "--state",
        "closed",
        "--json",
        "number,title,author,closedAt",
        "--limit",
        "1000",
        silent=True,
    )

    if closed_output:
        try:
            stats["closed"] = json.loads(closed_output)
        except json.JSONDecodeError:
            pass

    return stats


def get_file_diffs(repo_path, since):
    """Get all diffs for files changed in the specified time period, grouped by file."""
    # Get all commits from the specified time period
    log_output = run_git_command(
        repo_path, "log", f"--since={since}", "--pretty=format:%H"
    )

    if not log_output:
        return {}

    commit_hashes = log_output.split("\n")

    # Track files and their diffs across all commits
    file_diffs = defaultdict(list)

    for commit_hash in commit_hashes:
        if not commit_hash.strip():
            continue

        # Get the list of files changed in this commit
        files_output = run_git_command(
            repo_path, "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash
        )

        if not files_output:
            continue

        files = files_output.split("\n")

        for file_path in files:
            if not file_path.strip():
                continue

            # Get the diff for this specific file in this commit
            diff_output = run_git_command(
                repo_path, "show", commit_hash, "--", file_path
            )

            if diff_output:
                # Get commit info for context
                commit_info = run_git_command(
                    repo_path,
                    "show",
                    "--no-patch",
                    "--pretty=format:%h - %s (%ar)",
                    commit_hash,
                )

                file_diffs[file_path].append(
                    {"commit": commit_info, "diff": diff_output}
                )

    return file_diffs


def generate_github_summary_report(repo_path, since, period_description):
    """Generate a high-level GitHub summary report with issues and PRs."""
    repo_name = Path(repo_path).name

    # Get the GitHub repository URL
    repo_url = get_github_repo_url(repo_path)

    # Start building the markdown report
    report = []
    report.append(f"# GitHub Activity Summary for {repo_name}")
    report.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    report.append("")
    report.append(f"**Period:** {period_description}")
    report.append("")

    # Get GitHub statistics
    issue_stats = get_github_issues_stats(repo_path, since)
    pr_stats = get_github_pr_stats(repo_path, since)

    # Issues Summary
    report.append("## Issues Summary")
    report.append("")
    report.append(f"- **Issues Created:** {len(issue_stats['created'])}")
    report.append(f"- **Issues Updated:** {len(issue_stats['updated'])}")
    report.append(f"- **Issues Closed:** {len(issue_stats['closed'])}")
    report.append("")

    # Pull Requests Summary
    report.append("## Pull Requests Summary")
    report.append("")
    report.append(f"- **PRs Created:** {len(pr_stats['created'])}")
    report.append(f"- **PRs Updated:** {len(pr_stats['updated'])}")
    report.append(f"- **PRs Merged:** {len(pr_stats['merged'])}")
    report.append(f"- **PRs Closed (not merged):** {len(pr_stats['closed'])}")
    report.append("")

    # Detailed Issues List
    if issue_stats["created"]:
        report.append("## Issues Created")
        report.append("")
        for issue in issue_stats["created"]:
            author_login = (
                issue.get("author", {}).get("login", "Unknown")
                if isinstance(issue.get("author"), dict)
                else "Unknown"
            )
            issue_link = (
                f"[#{issue['number']}]({repo_url}/issues/{issue['number']})"
                if repo_url
                else f"#{issue['number']}"
            )
            report.append(f"- {issue_link}: {issue['title']} (by @{author_login})")
        report.append("")

    if issue_stats["closed"]:
        report.append("## Issues Closed")
        report.append("")
        for issue in issue_stats["closed"]:
            author_login = (
                issue.get("author", {}).get("login", "Unknown")
                if isinstance(issue.get("author"), dict)
                else "Unknown"
            )
            issue_link = (
                f"[#{issue['number']}]({repo_url}/issues/{issue['number']})"
                if repo_url
                else f"#{issue['number']}"
            )
            report.append(f"- {issue_link}: {issue['title']} (by @{author_login})")
        report.append("")

    # Detailed PRs List
    if pr_stats["created"]:
        report.append("## Pull Requests Created")
        report.append("")
        for pr in pr_stats["created"]:
            author_login = (
                pr.get("author", {}).get("login", "Unknown")
                if isinstance(pr.get("author"), dict)
                else "Unknown"
            )
            pr_link = (
                f"[#{pr['number']}]({repo_url}/pull/{pr['number']})"
                if repo_url
                else f"#{pr['number']}"
            )
            report.append(f"- {pr_link}: {pr['title']} (by @{author_login})")
        report.append("")

    if pr_stats["merged"]:
        report.append("## Pull Requests Merged")
        report.append("")
        for pr in pr_stats["merged"]:
            author_login = (
                pr.get("author", {}).get("login", "Unknown")
                if isinstance(pr.get("author"), dict)
                else "Unknown"
            )
            pr_link = (
                f"[#{pr['number']}]({repo_url}/pull/{pr['number']})"
                if repo_url
                else f"#{pr['number']}"
            )
            report.append(f"- {pr_link}: {pr['title']} (by @{author_login})")
        report.append("")

    if pr_stats["closed"]:
        report.append("## Pull Requests Closed (not merged)")
        report.append("")
        for pr in pr_stats["closed"]:
            author_login = (
                pr.get("author", {}).get("login", "Unknown")
                if isinstance(pr.get("author"), dict)
                else "Unknown"
            )
            pr_link = (
                f"[#{pr['number']}]({repo_url}/pull/{pr['number']})"
                if repo_url
                else f"#{pr['number']}"
            )
            report.append(f"- {pr_link}: {pr['title']} (by @{author_login})")
        report.append("")

    return "\n".join(report)


def show_help():
    """Display help information about the script usage."""
    help_text = """
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
"""
    print(help_text)


def generate_markdown_report(repo_path, since, period_description):
    """Generate a markdown report of git commits for the specified time period."""
    repo_name = Path(repo_path).name

    # Get the GitHub repository URL
    repo_url = get_github_repo_url(repo_path)

    # Start building the markdown report
    report = []
    report.append(f"# Git Commit Report for {repo_name}")
    report.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    report.append("")
    report.append(f"**Period:** {period_description}")
    report.append("")

    # Get commit counts
    commit_counts = get_commit_counts(repo_path, since)

    if not commit_counts:
        report.append("No commits found in the specified period.")
        return "\n".join(report)

    # Get file change statistics
    file_stats = get_file_change_stats(repo_path, since)

    # Display file change statistics at the top
    report.append("## File Changes")
    report.append("")
    report.append(f"- **Files Added:** {file_stats['added']}")
    report.append(f"- **Files Modified:** {file_stats['modified']}")
    report.append(f"- **Files Deleted:** {file_stats['deleted']}")
    report.append("")

    # Section 1: Commit counts by user
    report.append("## Commit Summary")
    report.append("")
    report.append("| Commits | Author |")
    report.append("|---------|--------|")

    for count, author in commit_counts:
        report.append(f"| {count} | {author} |")

    report.append("")

    # Section 2: Commit information grouped by user
    report.append("## Commits by Author")
    report.append("")

    commits_by_author = get_detailed_commits(repo_path, since)

    for author, commits in sorted(commits_by_author.items()):
        report.append(f"### {author}")
        report.append("")

        for commit in commits:
            commit_link = (
                f"[{commit['hash']}]({repo_url}/commit/{commit['hash']})"
                if repo_url
                else commit["hash"]
            )
            report.append(f"- [{commit_link}] {commit['subject']} *({commit['date']})*")

        report.append("")
        report.append("---")
        report.append("")

    # Section 3: File diffs for all changed files
    report.append("## File Diffs")
    report.append("")
    report.append("All changes to files in the specified period:")
    report.append("")

    file_diffs = get_file_diffs(repo_path, since)

    if file_diffs:
        for file_path in sorted(file_diffs.keys()):
            report.append(f"### {file_path}")
            report.append("")

            for diff_info in file_diffs[file_path]:
                report.append(f"**Commit:** {diff_info['commit']}")
                report.append("")
                report.append("```diff")
                report.append(diff_info["diff"])
                report.append("```")
                report.append("")

            report.append("---")
            report.append("")
    else:
        report.append("No file changes found in the specified period.")
        report.append("")

    return "\n".join(report)


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Generate Git and GitHub activity reports",
        add_help=False,  # We'll handle help ourselves
    )

    parser.add_argument("repo_path", nargs="?", help="Path to the Git repository")
    parser.add_argument(
        "--time-range",
        default="1.week",
        help="Time period for the report (default: 1.week)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where reports will be saved (default: current directory)",
    )
    parser.add_argument(
        "--report-type",
        choices=["all", "commits", "github"],
        default="all",
        help="Type of report to generate (default: all)",
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")

    # Parse arguments
    args = parser.parse_args()

    # Check for help flag
    if args.help or not args.repo_path:
        show_help()
        sys.exit(0 if args.help else 1)

    repo_path = args.repo_path
    since = args.time_range
    output_dir = args.output_dir
    report_type = args.report_type

    # Check if the path is a valid git repository
    if not Path(repo_path).is_dir():
        print(f"Error: {repo_path} is not a valid directory.")
        sys.exit(1)

    git_dir = Path(repo_path) / ".git"
    if not git_dir.exists():
        print(f"Error: {repo_path} is not a valid Git repository.")
        sys.exit(1)

    # Validate and create output directory if needed
    output_path = Path(output_dir).expanduser().resolve()
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error: Unable to create output directory {output_path}: {e}")
            sys.exit(1)
    elif not output_path.is_dir():
        print(f"Error: {output_path} is not a directory.")
        sys.exit(1)

    # Create a human-readable period description
    period_map = {
        "1.week": "Last 7 days",
        "2.weeks": "Last 14 days",
        "1.month": "Last 30 days",
        "2.months": "Last 60 days",
        "3.months": "Last 90 days",
        "6.months": "Last 180 days",
        "1.year": "Last 365 days",
    }
    period_description = period_map.get(since, f"Since {since}")

    # Create a filename-friendly version of the time range
    filename_period = since.replace(".", "")
    repo_name = Path(repo_path).name
    current_date = datetime.now().strftime("%Y%m%d")

    # Generate and save reports based on report type
    generated_reports = []

    if report_type in ["all", "commits"]:
        # Generate the commit report
        print(f"Generating commit report for {repo_name}...")
        commit_report = generate_markdown_report(repo_path, since, period_description)

        # Create output filename
        commit_filename = (
            f"{current_date}_{repo_name}_{filename_period}_commit_report.md"
        )
        commit_output_file = output_path / commit_filename

        # Write report to file
        with open(commit_output_file, "w") as f:
            f.write(commit_report)

        generated_reports.append(str(commit_output_file))
        print(f"✓ Commit report generated: {commit_output_file}")

    if report_type in ["all", "github"]:
        # Check if this is a GitHub repository
        if not is_github_repo(repo_path):
            print(f"⚠ Skipping GitHub summary: {repo_name} is not hosted on GitHub")
            if report_type == "github":
                print(
                    "Error: Cannot generate GitHub-only report for non-GitHub repository"
                )
                sys.exit(1)
        else:
            # Generate the GitHub summary report
            print(f"Generating GitHub summary for {repo_name}...")
            github_report = generate_github_summary_report(
                repo_path, since, period_description
            )

            # Create output filename
            github_filename = (
                f"{current_date}_{repo_name}_{filename_period}_github_summary.md"
            )
            github_output_file = output_path / github_filename

            # Write report to file
            with open(github_output_file, "w") as f:
                f.write(github_report)

            generated_reports.append(str(github_output_file))
            print(f"✓ GitHub summary generated: {github_output_file}")

    # Summary
    print(f"\n{'=' * 60}")
    print("Report generation complete!")
    print(f"Total reports generated: {len(generated_reports)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
