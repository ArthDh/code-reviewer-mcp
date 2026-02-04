#!/usr/bin/env python3
"""
Code Reviewer MCP Server

An MCP server that performs code reviews based on a developer persona.
This server analyzes git diffs and provides structured feedback following
established code review patterns and standards.

Copyright 2026, [Your Organization].
All rights reserved.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (required for stdio MCP servers)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("code-reviewer")

# Default persona file location (relative to repo root)
DEFAULT_PERSONA_PATH = "notebooks/code_reviewer_persona.md"

# ============================================================================
# CODE REVIEWER PERSONA (Embedded)
# ============================================================================

REVIEWER_PERSONA = """
# Code Review Standards

## Review Philosophy
Approach code review as a collaborative teaching moment, focusing on elevating 
code quality and establishing team standards. Be thorough and educational.

## Key Review Patterns

### 1. Documentation & Type Safety (HIGH PRIORITY)
- Every file must have a copyright header: `Copyright {year}, [Your Organization].`
- Return type hints are MANDATORY
- Use modern syntax: `str | None` over `Optional[str]`, `list[str]` over `List[str]`
- Avoid `Any` type - use `object` instead
- Functions require complete docstrings with Args and Returns

### 2. Code Organization & Imports
- NO relative imports - always use absolute paths
- Remove unused imports immediately
- Move magic numbers to constants at the top of file
- Use `StrEnums` for string keys used across the codebase
- Private methods should be prefixed with `_`

### 3. Data Structures & Return Types
- Prefer dataclasses over tuples for complex returns
- No random dictionaries - use TypedDict or Pydantic models
- "Define a custom data class with these as fields, Try not to return tuples"

### 4. Error Handling
- Catch SPECIFIC exceptions only - no bare `except:`
- Consolidate similar exception handling to reduce duplication
- Functions should handle edge cases (empty inputs, None values)

### 5. Code Readability
- Avoid ternary operators for complex logic - use explicit if/else
- Remove unused code and imports
- Don't leave commented-out code
- Don't use f-strings when no variables are interpolated

### 6. Performance & Resource Management
- Be mindful of serialization/deserialization costs
- Avoid unnecessary DataFrame copies
- Be careful with logger instantiation in Ray tasks

### 7. Architecture Concerns
- Don't call API layer methods from module layer
- Push common logic to templates/base classes
- Move hardcoded values to app config

### 8. Critical Questions to Ask
- "Do we need this?" - Question necessity of every addition
- "What happens if this is None?" - Check edge cases
- "Is this backwards compatible?" - Consider existing usage
- "Under what situation would this fail?" - Boundary conditions

### 9. Testing Standards
- Add test cases for bug fixes with ticket reference (IPLT-XXYY)
- Test edge cases
- Don't hardcode test values - use config files

## Common Callouts (use these exact phrases when applicable)
- "Missing File header"
- "Return type hint missing"
- "Move Magic numbers to the top of file as constants"
- "Define a custom data class with these as fields, Try not to return tuples"
- "No general exceptions"
- "Try to avoid ternary ops - they make the code harder to read"
- "Do we need this?"
- "Unused" / "Remove"
- "No relative paths, always specify absolute path for imports"
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def load_persona(
    persona_file: str | None = None,
    working_directory: str | None = None,
) -> str:
    """Load the code reviewer persona from a file or use embedded default.
    
    Args:
        persona_file: Path to persona markdown file (relative or absolute).
        working_directory: Working directory for resolving relative paths.
    
    Returns:
        The persona content as a string.
    """
    if not persona_file:
        # Try to find the default persona file
        cwd = working_directory or str(Path.cwd())
        repo_root = get_repo_root(cwd)
        if repo_root:
            default_path = Path(repo_root) / DEFAULT_PERSONA_PATH
            if default_path.exists():
                persona_file = str(default_path)
                logger.info(f"Using default persona file: {persona_file}")
    
    if persona_file:
        # Resolve relative paths
        file_path = Path(persona_file)
        if not file_path.is_absolute() and working_directory:
            file_path = Path(working_directory) / file_path
        
        try:
            content = file_path.read_text(encoding="utf-8")
            logger.info(f"Loaded persona from: {file_path}")
            return content
        except FileNotFoundError:
            logger.warning(f"Persona file not found: {file_path}, using embedded default")
        except Exception as e:
            logger.warning(f"Error reading persona file: {e}, using embedded default")
    
    # Fall back to embedded persona
    return REVIEWER_PERSONA


def run_git_command(args: list[str], cwd: str | None = None) -> tuple[str, str, int]:
    """Run a git command and return stdout, stderr, and return code.
    
    Args:
        args: Git command arguments (without 'git' prefix).
        cwd: Working directory for the command.
    
    Returns:
        Tuple of (stdout, stderr, return_code).
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=60,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


def get_repo_root(cwd: str | None = None) -> str | None:
    """Get the root directory of the git repository.
    
    Args:
        cwd: Working directory to start from.
    
    Returns:
        Path to repository root, or None if not in a git repo.
    """
    stdout, _, code = run_git_command(["rev-parse", "--show-toplevel"], cwd=cwd)
    if code == 0:
        return stdout.strip()
    return None


def get_current_branch(cwd: str | None = None) -> str | None:
    """Get the name of the current git branch.
    
    Args:
        cwd: Working directory.
    
    Returns:
        Current branch name, or None if not in a git repo.
    """
    stdout, _, code = run_git_command(["branch", "--show-current"], cwd=cwd)
    if code == 0:
        return stdout.strip()
    return None


def parse_diff_to_files(diff_output: str) -> dict[str, list[dict]]:
    """Parse git diff output into structured file changes.
    
    Args:
        diff_output: Raw git diff output.
    
    Returns:
        Dictionary mapping file paths to list of change hunks.
    """
    files: dict[str, list[dict]] = {}
    current_file = None
    current_hunk = None
    
    for line in diff_output.split("\n"):
        if line.startswith("diff --git"):
            # Extract filename from diff header
            parts = line.split(" b/")
            if len(parts) >= 2:
                current_file = parts[-1]
                files[current_file] = []
        elif line.startswith("@@") and current_file:
            # Parse hunk header for line numbers
            # Format: @@ -start,count +start,count @@
            try:
                hunk_info = line.split("@@")[1].strip()
                parts = hunk_info.split()
                old_range = parts[0] if parts else "-0"
                new_range = parts[1] if len(parts) > 1 else "+0"
                
                new_start = int(new_range.split(",")[0].replace("+", ""))
                
                current_hunk = {
                    "start_line": new_start,
                    "header": line,
                    "additions": [],
                    "deletions": [],
                    "context": [],
                }
                files[current_file].append(current_hunk)
            except (ValueError, IndexError):
                pass
        elif current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk["additions"].append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk["deletions"].append(line[1:])
            elif not line.startswith("\\"):
                current_hunk["context"].append(line)
    
    return files


def format_review_comment(
    file_path: str,
    line_number: int | None,
    comment: str,
    severity: str = "suggestion",
) -> str:
    """Format a review comment with file location.
    
    Args:
        file_path: Path to the file being reviewed.
        line_number: Line number for the comment, if applicable.
        comment: The review comment text.
        severity: One of 'critical', 'warning', 'suggestion', 'question'.
    
    Returns:
        Formatted comment string.
    """
    severity_icons = {
        "critical": "🔴",
        "warning": "🟡", 
        "suggestion": "💡",
        "question": "❓",
        "praise": "✅",
    }
    icon = severity_icons.get(severity, "💡")
    
    location = f"{file_path}"
    if line_number:
        location += f":{line_number}"
    
    return f"{icon} **{location}**\n{comment}\n"


# ============================================================================
# MCP TOOLS
# ============================================================================


@mcp.tool()
def get_branch_diff(
    base_branch: str = "development",
    file_filter: str = "*.py",
    working_directory: str | None = None,
) -> str:
    """Get the git diff between the current branch and a base branch.
    
    Args:
        base_branch: The base branch to compare against (default: development).
        file_filter: File pattern to filter (default: *.py for Python files).
        working_directory: Working directory (defaults to current directory).
    
    Returns:
        The git diff output showing changes on the current branch.
    """
    cwd = working_directory or str(Path.cwd())
    
    # Get current branch info
    current_branch = get_current_branch(cwd)
    if not current_branch:
        return "Error: Not in a git repository or unable to determine current branch."
    
    # Get the merge base to find where branches diverged
    stdout, stderr, code = run_git_command(
        ["merge-base", base_branch, "HEAD"],
        cwd=cwd,
    )
    if code != 0:
        return f"Error finding merge base: {stderr}"
    
    merge_base = stdout.strip()
    
    # Get the diff from merge base to HEAD for Python files
    stdout, stderr, code = run_git_command(
        ["diff", merge_base, "HEAD", "--", file_filter],
        cwd=cwd,
    )
    if code != 0:
        return f"Error getting diff: {stderr}"
    
    if not stdout.strip():
        return f"No changes found in {file_filter} files between {base_branch} and {current_branch}."
    
    # Add summary header
    summary = f"""## Branch Diff Summary

**Current Branch:** {current_branch}
**Base Branch:** {base_branch}
**Merge Base:** {merge_base[:8]}
**Filter:** {file_filter}

---

{stdout}
"""
    return summary


@mcp.tool()
def get_changed_files(
    base_branch: str = "development",
    file_filter: str = "*.py",
    working_directory: str | None = None,
) -> str:
    """Get a list of changed files on the current branch.
    
    Args:
        base_branch: The base branch to compare against (default: development).
        file_filter: File pattern to filter (default: *.py for Python files).
        working_directory: Working directory (defaults to current directory).
    
    Returns:
        List of changed file paths with change statistics.
    """
    cwd = working_directory or str(Path.cwd())
    
    # Get merge base
    stdout, stderr, code = run_git_command(
        ["merge-base", base_branch, "HEAD"],
        cwd=cwd,
    )
    if code != 0:
        return f"Error finding merge base: {stderr}"
    
    merge_base = stdout.strip()
    
    # Get changed files with stats
    stdout, stderr, code = run_git_command(
        ["diff", "--stat", "--name-only", merge_base, "HEAD", "--", file_filter],
        cwd=cwd,
    )
    if code != 0:
        return f"Error getting changed files: {stderr}"
    
    if not stdout.strip():
        return f"No {file_filter} files changed."
    
    files = [f.strip() for f in stdout.strip().split("\n") if f.strip()]
    
    # Get detailed stats
    stdout_stat, _, _ = run_git_command(
        ["diff", "--stat", merge_base, "HEAD", "--", file_filter],
        cwd=cwd,
    )
    
    return f"""## Changed Files ({len(files)} files)

### Files:
{chr(10).join(f'- `{f}`' for f in files)}

### Statistics:
```
{stdout_stat}
```
"""


@mcp.tool()
def review_diff(
    base_branch: str = "development",
    working_directory: str | None = None,
    focus_areas: str = "all",
    persona_file: str | None = None,
) -> str:
    """Review the git diff against the code review persona standards.
    
    This tool analyzes the diff between your current branch and the base branch,
    then provides structured feedback based on the team's code review standards.
    
    Args:
        base_branch: The base branch to compare against (default: development).
        working_directory: Working directory (defaults to current directory).
        focus_areas: Comma-separated focus areas: 'types', 'docs', 'style', 
                     'errors', 'performance', 'architecture', or 'all'.
        persona_file: Path to a custom reviewer persona markdown file.
                      Example: "notebooks/code_reviewer_persona.md"
                      If not provided, uses the default persona.
    
    Returns:
        A structured code review with comments organized by file and category.
    """
    cwd = working_directory or str(Path.cwd())
    
    # Load the persona
    persona = load_persona(persona_file, cwd)
    
    # Get the diff
    diff_result = get_branch_diff(base_branch, "*.py", cwd)
    if diff_result.startswith("Error") or "No changes found" in diff_result:
        return diff_result
    
    # Parse the diff into files
    files = parse_diff_to_files(diff_result)
    
    if not files:
        return "No files to review in the diff."
    
    # Build review context
    review_prompt = f"""
## Code Review Request

Please review the following diff using these standards:

{persona}

### Focus Areas: {focus_areas}

### Diff to Review:

{diff_result}

---

## Review Output Format

For each issue found, provide:
1. **File:Line** - The specific location
2. **Severity** - critical/warning/suggestion/question
3. **Issue** - What the problem is
4. **Suggestion** - How to fix it (with code example if helpful)

Organize by file, then by severity within each file.
"""
    
    return review_prompt


@mcp.tool()
def review_file(
    file_path: str,
    working_directory: str | None = None,
    persona_file: str | None = None,
) -> str:
    """Review a specific file against the code review persona standards.
    
    Args:
        file_path: Path to the file to review (relative or absolute).
        working_directory: Working directory (defaults to current directory).
        persona_file: Path to a custom reviewer persona markdown file.
                      Example: "notebooks/code_reviewer_persona.md"
                      If not provided, uses the default persona.
    
    Returns:
        Code review feedback for the specified file.
    """
    cwd = working_directory or str(Path.cwd())
    
    # Load the persona
    persona = load_persona(persona_file, cwd)
    
    # Resolve file path
    if not Path(file_path).is_absolute():
        file_path = str(Path(cwd) / file_path)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except Exception as e:
        return f"Error reading file: {e}"
    
    # Add line numbers
    lines = content.split("\n")
    numbered_content = "\n".join(
        f"{i+1:4d} | {line}" for i, line in enumerate(lines)
    )
    
    review_prompt = f"""
## Code Review Request - Single File

Please review this file using these standards:

{persona}

### File: `{file_path}`

```python
{numbered_content}
```

---

## Review Output Format

For each issue found, provide:
1. **Line Number** - The specific line(s)
2. **Severity** - critical/warning/suggestion/question  
3. **Issue** - What the problem is
4. **Suggestion** - How to fix it (with code example if helpful)

Start with a brief summary of the file's purpose, then list issues by severity.
"""
    
    return review_prompt


@mcp.tool()
def get_persona(
    persona_file: str | None = None,
    working_directory: str | None = None,
) -> str:
    """Get the code reviewer persona that will be used for reviews.
    
    Use this to view or verify the persona before running a review.
    
    Args:
        persona_file: Path to a custom reviewer persona markdown file.
                      Example: "notebooks/code_reviewer_persona.md"
                      If not provided, uses the default persona.
        working_directory: Working directory (defaults to current directory).
    
    Returns:
        The full persona content that will be used for code reviews.
    """
    cwd = working_directory or str(Path.cwd())
    persona = load_persona(persona_file, cwd)
    
    source = persona_file if persona_file else "embedded default"
    
    return f"""## Active Code Reviewer Persona

**Source:** {source}

---

{persona}
"""


@mcp.tool()
def get_review_checklist() -> str:
    """Get the full code review checklist based on the persona.
    
    Returns:
        A comprehensive checklist for manual code review.
    """
    return """
# Code Review Checklist

Use this checklist when reviewing Python code:

## Documentation & Type Safety
- [ ] File header present with correct year: `Copyright {year}, [Your Organization].`
- [ ] All functions have complete type hints (params + return)
- [ ] Modern Python type syntax (`str | None`, `list[str]`)
- [ ] No `Any` types without justification
- [ ] Docstrings complete with Args and Returns sections

## Code Organization
- [ ] Absolute imports only (no relative imports)
- [ ] Magic numbers moved to constants at top of file
- [ ] StrEnums used for repeated string keys
- [ ] Private methods prefixed with `_`
- [ ] Unused imports removed

## Data Structures
- [ ] Dataclasses used instead of tuples for complex returns
- [ ] TypedDict or Pydantic for dictionary structures
- [ ] No "random dictionaries" being passed around

## Error Handling
- [ ] Specific exception handling (no bare `except:`)
- [ ] Consolidated exception handling where appropriate
- [ ] Edge cases handled (None, empty inputs)

## Code Style
- [ ] Complex ternaries broken into if/else
- [ ] No unnecessary f-strings
- [ ] No commented-out code
- [ ] Unused code removed

## Performance
- [ ] No unnecessary DataFrame copies
- [ ] Serialization costs considered
- [ ] Logger instantiation appropriate (not in tight loops/Ray tasks)

## Architecture
- [ ] Layer separation maintained (API vs module layer)
- [ ] Common logic pushed to templates where appropriate
- [ ] Hardcoded values moved to config

## Testing
- [ ] Test coverage for new functionality
- [ ] Bug fix tests reference ticket (IPLT-XXYY)
- [ ] Edge cases tested

## Questions to Consider
- [ ] "Do we need this?" - Is every addition necessary?
- [ ] "What if this is None?" - Edge cases covered?
- [ ] "Is this backwards compatible?" - Existing usage considered?
"""


@mcp.tool()
def generate_review_report(
    base_branch: str = "development",
    output_file: str | None = None,
    working_directory: str | None = None,
    persona_file: str | None = None,
) -> str:
    """Generate a comprehensive code review report as a markdown file.
    
    Args:
        base_branch: The base branch to compare against (default: development).
        output_file: Path to write the report (default: .code_review.md in repo root).
        working_directory: Working directory (defaults to current directory).
        persona_file: Path to a custom reviewer persona markdown file.
                      Example: "notebooks/code_reviewer_persona.md"
                      If not provided, uses the default persona.
    
    Returns:
        Path to the generated report file and a summary.
    """
    cwd = working_directory or str(Path.cwd())
    repo_root = get_repo_root(cwd) or cwd
    current_branch = get_current_branch(cwd) or "unknown"
    
    # Load the persona
    persona = load_persona(persona_file, cwd)
    
    # Default output path
    if not output_file:
        output_file = str(Path(repo_root) / ".code_review.md")
    
    # Get changed files
    changed_files_output = get_changed_files(base_branch, "*.py", cwd)
    
    # Get diff
    diff_output = get_branch_diff(base_branch, "*.py", cwd)
    
    # Generate report content
    report = f"""# Code Review Report

**Branch:** {current_branch}
**Base:** {base_branch}
**Persona:** {persona_file or 'default (embedded)'}
**Generated:** {__import__('datetime').datetime.now().isoformat()}

---

{changed_files_output}

---

## Review Standards

{persona}

---

## Diff to Review

{diff_output}

---

## Review Checklist

{get_review_checklist()}
"""
    
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        return f"Report generated successfully: `{output_file}`\n\nYou can now review the diff above and provide feedback following the persona standards."
    except Exception as e:
        return f"Error writing report: {e}\n\nReport content:\n{report[:2000]}..."


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main() -> None:
    """Run the MCP server."""
    logger.info("Starting Code Reviewer MCP Server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
