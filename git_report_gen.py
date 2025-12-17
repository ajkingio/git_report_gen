#!/usr/bin/env python3

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


def generate_markdown_report(repo_path, since, period_description):
    """Generate a markdown report of git commits for the specified time period."""
    repo_name = Path(repo_path).name

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
        report.append(f"No commits found in the specified period.")
        return "\n".join(report)

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
            report.append(
                f"- [{commit['hash']}] {commit['subject']} *({commit['date']})*"
            )

        report.append("")
        report.append("---")
        report.append("")

    # Section 3: File diffs for all changed files
    report.append("## File Diffs")
    report.append("")
    report.append(f"All changes to files in the specified period:")
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
        report.append(f"No file changes found in the specified period.")
        report.append("")

    return "\n".join(report)


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python3 git_report_gen.py /path/to/repo [time_range]")
        print("Examples:")
        print("  python3 git_report_gen.py /path/to/repo           # Last 1 week (default)")
        print("  python3 git_report_gen.py /path/to/repo 2.weeks   # Last 2 weeks")
        print("  python3 git_report_gen.py /path/to/repo 1.month   # Last 1 month")
        print("  python3 git_report_gen.py /path/to/repo 3.months  # Last 3 months")
        print("  python3 git_report_gen.py /path/to/repo 1.year    # Last 1 year")
        sys.exit(1)

    repo_path = sys.argv[1]
    since = "1.week" if len(sys.argv) == 2 else sys.argv[2]

    # Check if the path is a valid git repository
    if not Path(repo_path).is_dir():
        print(f"Error: {repo_path} is not a valid directory.")
        sys.exit(1)

    git_dir = Path(repo_path) / ".git"
    if not git_dir.exists():
        print(f"Error: {repo_path} is not a valid Git repository.")
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

    # Generate the report
    report = generate_markdown_report(repo_path, since, period_description)

    # Create output filename with current date, repo name, and time range
    repo_name = Path(repo_path).name
    current_date = datetime.now().strftime("%Y%m%d")
    output_filename = f"{current_date}_{repo_name}_{filename_period}_commit_report.md"

    # Write report to file
    with open(output_filename, "w") as f:
        f.write(report)

    print(f"Report generated: {output_filename}")


if __name__ == "__main__":
    main()
