# Code Reviewer MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)

An MCP (Model Context Protocol) server that performs automated code reviews based on customizable reviewer personas. Integrates seamlessly with Cursor IDE and other MCP-compatible tools.

## Overview

This server provides automated code review capabilities by analyzing git diffs against configurable review standards. It supports custom reviewer personas, making it easy to enforce team-specific code quality standards.

## Features

The server exposes 7 tools:

| Tool | Description |
|------|-------------|
| `get_branch_diff` | Get git diff between current branch and base branch |
| `get_changed_files` | List files changed on current branch with stats |
| `review_diff` | Get diff with review context and persona standards |
| `review_file` | Review a specific file against standards |
| `get_persona` | View the active reviewer persona |
| `get_review_checklist` | Get the full review checklist |
| `generate_review_report` | Generate a markdown review report file |

### Custom Persona Support

All review tools accept a `persona_file` parameter to use a custom reviewer persona:

```
persona_file: "personas/example_persona.md"
```

**Default locations** (checked in order):
1. `personas/example_persona.md` in the MCP server directory
2. `notebooks/code_reviewer_persona.md` in your project root (for backward compatibility)
3. Embedded default persona (if no file found)

**Example persona:** See `personas/example_persona.md` for a complete example of a reviewer persona.

## Installation

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

1. **Install dependencies:**
   ```bash
   cd code-reviewer-mcp
   uv sync  # or: pip install -r requirements.txt
   ```

2. **Set up the Cursor rule** (optional but recommended):
   
   Copy the template rule to your project's `.cursor/rules/` directory:
   ```bash
   mkdir -p .cursor/rules
   cp tools/code-reviewer-mcp/.cursor/rules/code-review.mdc.template .cursor/rules/code-review.mdc
   ```
   
   Then customize it for your project's review standards.

3. **Configure in Cursor** by adding to `~/.cursor/mcp.json`:

   ```json
   {
     "mcpServers": {
       "code-reviewer": {
         "command": "uv",
         "args": [
           "--directory",
           "/path/to/code-reviewer-mcp",
           "run",
           "server.py"
         ]
       }
     }
   }
   ```

   Or if using pip:
   ```json
   {
     "mcpServers": {
       "code-reviewer": {
         "command": "python",
         "args": [
           "/path/to/code-reviewer-mcp/server.py"
         ]
       }
     }
   }
   ```

## Architecture

The code reviewer consists of two components:

1. **MCP Server** (`server.py`): Provides the tools (`get_branch_diff`, `review_diff`, etc.)
2. **Cursor Rule** (`.cursor/rules/code-review.mdc`): Provides workflow instructions and review standards

The MCP server is **reusable** across projects - it provides generic code review tools.  
The Cursor rule is **project-specific** - it defines your team's review standards and workflow.

When you ask for a code review, the Cursor rule instructs the AI on:
- Which MCP tools to call and in what order
- What standards to check against
- How to format the output

## Usage in Cursor

### Quick Start

1. **Restart Cursor** after installation to load the new MCP server
2. Ask Claude to review your code:
   - "Review my current branch"
   - "Review this PR against development"
   - "Check this file for issues"

### Example Commands

**Basic usage (uses default persona):**
```
"Review the changes on my branch"
"Get the diff against development"
"Review src/my_module/file.py"
"Generate a code review report"
```

**With custom persona (using @ reference):**
```
"Review my code using @personas/example_persona.md"
"Review this file using the persona at @path/to/strict_reviewer.md"
"Generate a review report with @personas/example_persona.md"
```

The `@file` syntax in Cursor expands the file reference, making it easy to 
select different reviewer personas for different review styles.

### Using the Cursor Rule

A Cursor rule at `.cursor/rules/code-review.mdc` automatically triggers 
the reviewer when you say "review", "code review", or "PR review".

**What the rule does:**
- Provides step-by-step workflow instructions for using the MCP tools
- Defines the review standards and checklist (type safety, documentation, etc.)
- Specifies the output format for reviews
- Handles persona file selection via `@` syntax

**For this project:** The rule is located at `.cursor/rules/code-review.mdc` in the repo root.

**For other projects:** A template rule file is included at `tools/code-reviewer-mcp/.cursor/rules/code-review.mdc.template`. Copy it to your project's `.cursor/rules/` directory and customize it for your team's standards.

The rule provides:
- **Workflow instructions**: Step-by-step guide on how to use the MCP tools
- **Review standards**: Checklist of what to check (can be customized per project)
- **Output format**: Structure for review comments
- **Integration guidance**: How to combine with Bitbucket MCP for PR comments

## Persona Files

### How Persona Selection Works

1. **Explicit selection**: Pass `persona_file` parameter with the path
2. **Default locations** (checked in order):
   - `personas/example_persona.md` in the MCP server directory
   - `notebooks/code_reviewer_persona.md` in your project root (for backward compatibility)
3. **Embedded fallback**: Uses built-in persona if no file found

**Example persona:** See `personas/example_persona.md` for a complete example based on real code review patterns.

### Creating a Custom Persona

Create a markdown file with your review standards. Example structure:

```markdown
# Code Reviewer Persona: [Name]

## Review Philosophy
[Your approach to code review]

## Key Standards
### Type Safety
- [Your type checking rules]

### Documentation
- [Your documentation requirements]

### Code Style
- [Your style preferences]

## Common Callouts
- "Missing type hint" → Add type annotations
- "No tests" → Add test coverage
```

### Switching Personas

You can have multiple persona files for different contexts. Store them in the `personas/` directory:
- `personas/example_persona.md` - Example persona (included with this repo)
- `personas/strict_reviewer.md` - For production code (create your own)
- `personas/junior_friendly.md` - Educational, more explanatory (create your own)
- `personas/security_focused.md` - Emphasis on security patterns (create your own)

Start with `personas/example_persona.md` and customize it for your team's needs.

## Default Review Standards

The embedded default persona checks for:

### Type Safety
- Complete type hints on all functions
- Modern syntax (`str | None` over `Optional`)
- No `Any` types without justification

### Documentation
- File headers with copyright
- Complete docstrings with Args/Returns

### Code Organization
- Absolute imports only
- Magic numbers as constants
- Unused code removed

### Error Handling
- Specific exceptions only
- Edge cases handled

### Architecture
- Layer separation maintained
- Common logic in templates

## Utilities

### Export PR Comments

The `utils/export_comments.py` script helps export your Bitbucket PR comments to CSV for analysis
or building training data for code review personas.

**Usage:**
```bash
# Set environment variables (recommended)
export ATLASSIAN_EMAIL="your-email@example.com"
export BITBUCKET_API_TOKEN="your-api-token"
export BITBUCKET_WORKSPACE="your-workspace"
export BITBUCKET_REPO_SLUG="your-repo"
export BITBUCKET_ACCOUNT_ID="your-account-id"  # Optional: filter to your comments only

# Export comments (from the code-reviewer-mcp directory)
python utils/export_comments.py

# Export only your comments (with account ID filter)
python utils/export_comments.py --account-id your-account-id

# Export all comments (no filter)
python utils/export_comments.py --account-id ""

# Or pass everything as arguments
python utils/export_comments.py \
  --email your-email@example.com \
  --token your-token \
  --workspace your-workspace \
  --repo your-repo \
  --output my_comments.csv \
  --account-id your-account-id
```

**Note**: This utility requires the `requests` library. Install with:
```bash
pip install requests
# or
uv add requests
```

**Output:** The script generates a CSV file with columns:
- `pr_id`, `pr_title`, `pr_url`
- `comment_id`, `content`
- `file_path`, `line` (for inline comments)
- `created_on`, `updated_on`

## Development

### Testing the Server

```bash
cd code-reviewer-mcp
uv run server.py
```

The server communicates via stdio, so you'll see it waiting for JSON-RPC messages.

### Modifying the Persona

The reviewer persona is embedded in `server.py` in the `REVIEWER_PERSONA` constant.
Update this to change review standards.

## Limitations

- **No inline comments**: Cursor doesn't have an API to programmatically add 
  inline comments to files. The server outputs reviews with file:line references 
  that you can navigate to.
  
- **Python-focused**: Currently filters for `*.py` files by default. The 
  `file_filter` parameter can be changed to include other file types.

## Troubleshooting

### Server not appearing in Cursor

1. Check `~/.cursor/mcp.json` has the correct path
2. Restart Cursor completely (Cmd+Q on macOS)
3. Check the MCP logs: `~/Library/Logs/Claude/mcp*.log`

### Git errors

Ensure you're in a git repository when using the diff-related tools.
The server needs access to git commands.

## Optional: Bitbucket Integration

For teams using Bitbucket, you can optionally configure the `@lexmata/bitbucket-mcp` server
to enable programmatic PR comment creation. This allows you to post review comments
directly to Bitbucket pull requests.

### Setting up Bitbucket MCP

1. **Install the Bitbucket MCP server** (if not already installed):
   ```bash
   npm install -g @lexmata/bitbucket-mcp
   ```

2. **Configure in `~/.cursor/mcp.json`**:
   ```json
   {
     "mcpServers": {
       "code-reviewer": {
         "command": "uv",
         "args": ["--directory", "/path/to/code-reviewer-mcp", "run", "server.py"]
       },
       "bitbucket": {
         "command": "npx",
         "args": ["-y", "@lexmata/bitbucket-mcp"],
         "env": {
           "BITBUCKET_WORKSPACE": "your-workspace",
           "BITBUCKET_REPO_SLUG": "your-repo",
           "BITBUCKET_APP_PASSWORD": "your-app-password"
         }
       }
     }
   }
   ```

3. **Usage**: Once configured, you can use Bitbucket MCP tools alongside the code reviewer:
   - Create PR comments programmatically
   - Fetch PR details
   - Post review feedback directly to Bitbucket

   Example workflow:
   ```
   1. Use code-reviewer tools to generate review feedback
   2. Use bitbucket-mcp tools to post comments to the PR
   ```

   **Note**: This integration is optional. The code reviewer works perfectly fine without it,
   generating review reports that you can manually copy to PR comments.
