"""
Export Bitbucket PR comments to CSV.

This utility script helps export your code review comments from Bitbucket PRs
for analysis or to build training data for code review personas.

Usage:
    # Set environment variables (recommended):
    export ATLASSIAN_EMAIL="your-email@example.com"
    export BITBUCKET_API_TOKEN="your-api-token"
    
    # Or pass credentials directly:
    python utils/export_comments.py --email your-email --token your-token --workspace your-workspace --repo your-repo
    
    # With account ID filter (to export only your comments):
    python utils/export_comments.py --email your-email --token your-token --workspace your-workspace --repo your-repo --account-id your-account-id

Required API token scopes:
    - read:repository:bitbucket
    - read:pullrequest:bitbucket

To find your account ID:
    1. Visit https://bitbucket.org/account/settings/app-passwords/
    2. Create an app password with the required scopes
    3. Your account ID can be found in the Bitbucket API response when fetching your user info
"""

import argparse
import csv
import os
import sys
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configuration (can be overridden via command line or environment variables)
WORKSPACE = "your-workspace"  # Default workspace name
REPO_SLUG = "your-repo"  # Default repository slug
TARGET_ACCOUNT_ID = ""  # Default account ID (empty = export all comments)

# CSV field names (ordered)
CSV_FIELDS = [
    "pr_id",
    "pr_title",
    "pr_url",
    "comment_id",
    "content",
    "file_path",
    "line",
    "created_on",
    "updated_on",
]


def create_session(email: str, token: str) -> requests.Session:
    """Create a requests session with retry logic and auth configured."""
    session = requests.Session()
    session.auth = (email, token)
    
    # Configure retries for transient failures
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session


def fetch_paginated(
    session: requests.Session, 
    url: str, 
    label: str = "items",
    show_progress: bool = True,
) -> list[dict[str, Any]]:
    """Fetch all pages from a paginated Bitbucket API endpoint."""
    results = []
    page = 1
    
    while url:
        if show_progress:
            print(f"\r  Fetching {label}... (page {page}, {len(results)} so far)", end="", flush=True)
        
        response = session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        results.extend(data.get("values", []))
        url = data.get("next")
        page += 1
    
    if show_progress:
        print(f"\r  Fetched {len(results)} {label}" + " " * 20)  # Clear line
    
    return results


def get_all_prs(session: requests.Session, workspace: str, repo_slug: str) -> list[dict[str, Any]]:
    """Fetch all pull requests (merged, open, and declined)."""
    base_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}"
    url = f"{base_url}/pullrequests?state=MERGED&state=OPEN&state=DECLINED"
    return fetch_paginated(session, url, label="pull requests")


def get_pr_comments(session: requests.Session, workspace: str, repo_slug: str, pr_id: int) -> list[dict[str, Any]]:
    """Fetch all comments for a specific PR."""
    base_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}"
    url = f"{base_url}/pullrequests/{pr_id}/comments"
    return fetch_paginated(session, url, show_progress=False)


def export_comments_to_csv(
    session: requests.Session,
    workspace: str,
    repo_slug: str,
    output_file: str = "my_pr_comments.csv",
    account_id: str | None = None,
) -> int:
    """
    Export PR comments to CSV, optionally filtered by account_id.
    
    Args:
        session: Authenticated requests session
        workspace: Bitbucket workspace name
        repo_slug: Repository slug
        output_file: Path to output CSV file
        account_id: Filter to only include comments from this user (None = all comments)
        
    Returns:
        Number of comments exported
    """
    all_comments = []
    pr_web_url = f"https://bitbucket.org/{workspace}/{repo_slug}/pull-requests"
    
    print("Fetching pull requests...")
    prs = get_all_prs(session, workspace, repo_slug)
    total_prs = len(prs)
    print(f"Found {total_prs} PRs to scan\n")
    
    for idx, pr in enumerate(prs, 1):
        pr_id = pr["id"]
        pr_title = pr["title"]
        
        # Progress indicator
        print(f"\r[{idx}/{total_prs}] Scanning PR #{pr_id}: {pr_title[:50]}...", end="", flush=True)
        
        comments = get_pr_comments(session, workspace, repo_slug, pr_id)
        
        for comment in comments:
            # Filter by account_id if provided
            if account_id:
                author_id = comment.get("user", {}).get("account_id", "")
                if author_id != account_id:
                    continue
            
            all_comments.append({
                "pr_id": pr_id,
                "pr_title": pr_title,
                "pr_url": f"{pr_web_url}/{pr_id}",
                "comment_id": comment.get("id"),
                "content": comment.get("content", {}).get("raw", ""),
                "file_path": comment.get("inline", {}).get("path", "General comment"),
                "line": comment.get("inline", {}).get("to", ""),
                "created_on": comment.get("created_on", ""),
                "updated_on": comment.get("updated_on", ""),
            })
        
        # Small delay to be nice to the API
        time.sleep(0.1)
    
    print("\n")  # New line after progress
    
    # Write to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_comments)
    
    print(f"Exported {len(all_comments)} comments to {output_file}")
    return len(all_comments)


def main():
    parser = argparse.ArgumentParser(
        description="Export your Bitbucket PR comments to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-e", "--email",
        default=os.environ.get("ATLASSIAN_EMAIL"),
        help="Atlassian account email (or set ATLASSIAN_EMAIL env var)",
    )
    parser.add_argument(
        "-t", "--token",
        default=os.environ.get("BITBUCKET_API_TOKEN"),
        help="Bitbucket API token (or set BITBUCKET_API_TOKEN env var)",
    )
    parser.add_argument(
        "-w", "--workspace",
        default=os.environ.get("BITBUCKET_WORKSPACE", WORKSPACE),
        help="Bitbucket workspace (or set BITBUCKET_WORKSPACE env var). Required if not set via env var.",
    )
    parser.add_argument(
        "-r", "--repo",
        default=os.environ.get("BITBUCKET_REPO_SLUG", REPO_SLUG),
        help="Repository slug (or set BITBUCKET_REPO_SLUG env var). Required if not set via env var.",
    )
    parser.add_argument(
        "-o", "--output",
        default="my_pr_comments.csv",
        help="Output CSV file path (default: my_pr_comments.csv)",
    )
    parser.add_argument(
        "-a", "--account-id",
        default=os.environ.get("BITBUCKET_ACCOUNT_ID", TARGET_ACCOUNT_ID),
        help="Filter comments by account ID (or set BITBUCKET_ACCOUNT_ID env var). Set to empty string to export all comments. Default: export all comments.",
    )
    
    args = parser.parse_args()
    
    # Validate credentials
    if not args.email or not args.token:
        print("Error: Missing credentials.", file=sys.stderr)
        print("Provide --email and --token, or set ATLASSIAN_EMAIL and BITBUCKET_API_TOKEN environment variables.", file=sys.stderr)
        sys.exit(1)
    
    # Validate workspace and repo (must not be placeholder values)
    if args.workspace == "your-workspace" or args.repo == "your-repo":
        print("Error: Workspace and repository must be specified.", file=sys.stderr)
        print("Provide --workspace and --repo, or set BITBUCKET_WORKSPACE and BITBUCKET_REPO_SLUG environment variables.", file=sys.stderr)
        sys.exit(1)
    
    # Handle empty account_id (export all comments)
    account_id = args.account_id if args.account_id else None
    
    # Create session and export
    session = create_session(args.email, args.token)
    
    try:
        export_comments_to_csv(
            session, 
            args.workspace, 
            args.repo, 
            args.output, 
            account_id
        )
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Error: Authentication failed. Check your email and API token.", file=sys.stderr)
        elif e.response.status_code == 403:
            print("Error: Access denied. Ensure your API token has the required scopes:", file=sys.stderr)
            print("  - read:repository:bitbucket", file=sys.stderr)
            print("  - read:pullrequest:bitbucket", file=sys.stderr)
        else:
            print(f"Error: API request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: Network error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
