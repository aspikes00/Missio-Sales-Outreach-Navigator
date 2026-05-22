#!/bin/bash

echo ""
echo "======================================"
echo "  Missio Outreach — First-Time Setup"
echo "======================================"
echo ""

# ── Homebrew ──────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
  echo "Installing Homebrew (this takes a few minutes)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
  fi
  echo "✓ Homebrew installed."
else
  echo "✓ Homebrew already installed."
fi

# ── Python ────────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null || ! python3 -c "import sys; assert sys.version_info >= (3,11)" 2>/dev/null; then
  echo "Installing Python 3.11+..."
  brew install python
  echo "✓ Python installed."
else
  echo "✓ Python $(python3 --version | cut -d' ' -f2) already installed."
fi

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "Creating isolated Python environment..."
  python3 -m venv .venv
  echo "✓ Virtual environment created."
else
  echo "✓ Virtual environment already exists."
fi

PYTHON=".venv/bin/python3"
PIP=".venv/bin/pip"

# ── Python packages ───────────────────────────────────────────────────────────
echo "Installing required packages (about a minute)..."
$PIP install -r requirements.txt -q
echo "✓ Packages installed."

# ── Playwright browser ────────────────────────────────────────────────────────
echo "Installing browser (Chromium)..."
$PYTHON -m playwright install chromium
echo "✓ Browser installed."

# ── .env file ─────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "======================================"
  echo "  ACTION REQUIRED: Fill in your .env"
  echo "======================================"
  echo ""
  echo "Opening .env in TextEdit — fill in your LinkedIn login and Anthropic API key..."
  sleep 1
  open -e .env
  echo ""
  echo "Fill in:"
  echo "  LINKEDIN_EMAIL    — your LinkedIn email"
  echo "  LINKEDIN_PASSWORD — your LinkedIn password"
  echo "  ANTHROPIC_API_KEY — from console.anthropic.com"
  echo ""
  echo "Save the file, then press Enter to continue..."
  read -r
else
  echo "✓ .env file already exists."
fi

# ── Brand config check ────────────────────────────────────────────────────────
if grep -q "YOUR_MISSIO_LIST_ID_HERE" brands/missio/brand.toml; then
  echo ""
  echo "=========================================="
  echo "  ACTION REQUIRED: Fill in brand.toml"
  echo "=========================================="
  echo ""
  echo "Opening brands/missio/brand.toml in TextEdit..."
  sleep 1
  open -e brands/missio/brand.toml
  echo ""
  echo "Fill in:"
  echo "  sales_nav_list_url   — your Sales Navigator list URL"
  echo "  sales_nav_list_name  — exact name of your list in Sales Navigator"
  echo "  sales_nav_search_url — your Sales Navigator search URL"
  echo ""
  echo "Save the file, then press Enter to continue..."
  read -r
else
  echo "✓ Brand config already filled in."
fi

echo ""
echo "======================================"
echo "  Setup complete!"
echo "======================================"
echo ""
echo "Next step: run  bash missio.sh  every day."
echo ""
