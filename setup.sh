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
  # Add Homebrew to PATH for Apple Silicon Macs
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

# ── Python packages ───────────────────────────────────────────────────────────
echo ""
echo "Installing required packages (this takes about a minute)..."
python3 -m pip install -r requirements.txt -q
echo "✓ Packages installed."

# ── Playwright browser ────────────────────────────────────────────────────────
echo "Installing browser (Chromium)..."
python3 -m playwright install chromium
echo "✓ Browser installed."

# ── .env file ─────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "======================================"
  echo "  ACTION REQUIRED: Fill in your .env"
  echo "======================================"
  echo ""
  echo "Your .env file was created. You need to fill in 3 values."
  echo "Opening it now in TextEdit..."
  sleep 1
  open -e .env
  echo ""
  echo "Fill in:"
  echo "  LINKEDIN_EMAIL    — your LinkedIn login email"
  echo "  LINKEDIN_PASSWORD — your LinkedIn password"
  echo "  ANTHROPIC_API_KEY — your Anthropic API key (from console.anthropic.com)"
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
  echo "You need to fill in 3 values in that file:"
  echo ""
  echo "  sales_nav_list_url   — go to your Sales Navigator list, copy the URL"
  echo "  sales_nav_list_name  — the exact name of your list in Sales Navigator"
  echo "  sales_nav_search_url — go to your Sales Nav search, copy the URL"
  echo ""
  echo "Save the file, then press Enter to continue..."
  read -r
else
  echo "✓ Brand config already filled in."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "======================================"
echo "  Setup complete!"
echo "======================================"
echo ""
echo "Next step: run  bash missio.sh  every day."
echo ""
