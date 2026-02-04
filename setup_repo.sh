#!/bin/bash
# Setup script to initialize this directory as a standalone git repository

set -e

echo "🚀 Setting up code-reviewer-mcp as standalone repository..."

# Check if already a git repo
if [ -d ".git" ]; then
    echo "⚠️  Already a git repository. Removing existing .git directory..."
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    rm -rf .git
fi

# Initialize git
echo "📦 Initializing git repository..."
git init

# Add all files
echo "📝 Adding files..."
git add .

# Create initial commit
echo "💾 Creating initial commit..."
git commit -m "Initial commit: Code Reviewer MCP Server

- MCP server for automated code reviews
- Customizable reviewer personas
- Cursor IDE integration
- Bitbucket PR comment export utility"

# Set default branch to main
git branch -M main

echo ""
echo "✅ Repository initialized!"
echo ""
echo "Next steps:"
echo "1. Create a repository on GitHub: https://github.com/new"
echo "2. Run: git remote add origin https://github.com/YOUR_USERNAME/code-reviewer-mcp.git"
echo "3. Run: git push -u origin main"
echo ""
echo "Or use GitHub CLI:"
echo "  gh repo create code-reviewer-mcp --public --source=. --remote=origin --push"
echo ""
