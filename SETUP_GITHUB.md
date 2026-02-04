# Setting Up as a Standalone GitHub Repository

This guide explains how to publish this code-reviewer-mcp directory as a standalone public GitHub repository.

## Prerequisites

- GitHub account
- Git installed locally
- GitHub CLI (`gh`) installed (optional, but recommended)

## Option 1: Using GitHub CLI (Recommended)

1. **Navigate to the directory:**
   ```bash
   cd tools/code-reviewer-mcp
   ```

2. **Initialize git repository (if not already done):**
   ```bash
   git init
   ```

3. **Create initial commit:**
   ```bash
   git add .
   git commit -m "Initial commit: Code Reviewer MCP Server"
   ```

4. **Create GitHub repository and push:**
   ```bash
   gh repo create code-reviewer-mcp --public --source=. --remote=origin --push
   ```

## Option 2: Manual Setup

1. **Navigate to the directory:**
   ```bash
   cd tools/code-reviewer-mcp
   ```

2. **Initialize git repository:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Code Reviewer MCP Server"
   ```

3. **Create repository on GitHub:**
   - Go to https://github.com/new
   - Repository name: `code-reviewer-mcp`
   - Description: "MCP server for automated code reviews based on customizable reviewer personas"
   - Visibility: **Public**
   - Do NOT initialize with README, .gitignore, or license (we already have these)
   - Click "Create repository"

4. **Add remote and push:**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/code-reviewer-mcp.git
   git branch -M main
   git push -u origin main
   ```

## Option 3: Extract from Parent Repo

If this directory is currently part of a larger git repository, you can extract it:

1. **Use git subtree or filter-branch:**
   ```bash
   cd /path/to/parent/repo
   git subtree push --prefix=tools/code-reviewer-mcp origin code-reviewer-mcp
   ```

2. **Or use git filter-repo (recommended):**
   ```bash
   # Install git-filter-repo if needed
   pip install git-filter-repo
   
   # Extract the subdirectory
   git filter-repo --path tools/code-reviewer-mcp --to-subdirectory-filter /
   ```

## After Publishing

1. **Add topics/tags on GitHub:**
   - `mcp`
   - `code-review`
   - `cursor`
   - `ai-code-review`
   - `python`

2. **Update README if needed:**
   - Add badges (build status, license, etc.)
   - Add installation instructions
   - Add contribution guidelines

3. **Create a release:**
   ```bash
   git tag -a v1.0.0 -m "Initial release"
   git push origin v1.0.0
   ```

## Notes

- Make sure to remove any sensitive information before publishing
- The `.venv/` directory is already in `.gitignore`
- Consider adding a `CONTRIBUTING.md` file for open source contributions
