#!/bin/bash

# Add Homebrew to PATH (Apple Silicon Macs)
if [[ -f /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Use the project's isolated Python environment
PYTHON=".venv/bin/python3"

# If the venv doesn't exist yet, tell the user to run setup first
if [ ! -f "$PYTHON" ]; then
  echo ""
  echo "  Setup not complete. Run this first:"
  echo "    bash setup.sh"
  echo ""
  exit 1
fi

clear
echo ""
echo "======================================="
echo "   Missio LinkedIn Outreach Agent"
echo "======================================="
echo ""
echo "  0)  Import my Sales Nav list          (first-time setup — loads your existing list)"
echo "  1)  Fill my Sales Nav list           (adds ~200 more leads from your search)"
echo "  2)  Preview today's messages         (dry run — nothing sent)"
echo "  3)  Run today's outreach             (sends connections + messages)"
echo ""
echo "  4)  Check pipeline status"
echo "  5)  Today's report"
echo "  6)  This week's report"
echo "  7)  Save today's report to a file"
echo "  8)  Save this week's report to a file"
echo ""
echo "  9)  Mark a lead as booked"
echo "  10) Mark a lead as do-not-contact"
echo ""
echo "  11) Voice memo queue              (scripts to record on LinkedIn mobile)"
echo "  12) Mark a voice memo as sent"
echo ""
echo "  q)  Quit"
echo ""
printf "  What would you like to do? "
read -r choice

echo ""

case "$choice" in

  0)
    echo "Opening your Sales Navigator list and importing leads..."
    echo "(Browser will open — this reads your existing list, nothing is sent.)"
    echo ""
    $PYTHON main.py sync-list --brand missio
    ;;

  1)
    echo "Opening browser to fill your Sales Navigator list..."
    echo "(Adds up to 200 leads. Run it again tomorrow to continue.)"
    echo ""
    $PYTHON main.py populate-list --brand missio
    ;;

  2)
    echo "Generating today's messages in preview mode..."
    echo "(Nothing will be sent — just showing you what Claude would write.)"
    echo ""
    $PYTHON main.py run --brand missio --dry-run
    ;;

  3)
    echo "Starting today's outreach session..."
    echo "(Browser will open. You can minimize it — don't close it.)"
    echo ""
    $PYTHON main.py run --brand missio
    ;;

  4)
    $PYTHON main.py status --brand missio
    ;;

  5)
    $PYTHON main.py report --brand missio
    ;;

  6)
    $PYTHON main.py report --brand missio --week
    ;;

  7)
    $PYTHON main.py report --brand missio --save
    echo ""
    echo "Report saved to logs/reports/"
    ;;

  8)
    $PYTHON main.py report --brand missio --week --save
    echo ""
    echo "Report saved to logs/reports/"
    ;;

  9)
    echo ""
    printf "  Paste the LinkedIn profile URL of the person who booked: "
    read -r url
    printf "  Any notes? (press Enter to skip): "
    read -r notes
    if [ -n "$notes" ]; then
      $PYTHON main.py mark-booked --brand missio --url "$url" --notes "$notes"
    else
      $PYTHON main.py mark-booked --brand missio --url "$url"
    fi
    ;;

  10)
    echo ""
    printf "  Paste the LinkedIn profile URL to add to do-not-contact: "
    read -r url
    $PYTHON main.py mark-dnc --url "$url"
    ;;

  11)
    echo "Fetching voice memo queue..."
    echo "(These are short scripts to read aloud on LinkedIn mobile as voice notes.)"
    echo ""
    $PYTHON main.py voice-queue --brand missio
    ;;

  12)
    echo ""
    printf "  Enter the Log ID from the voice memo queue: "
    read -r log_id
    $PYTHON main.py mark-voice-sent --brand missio --log-id "$log_id"
    ;;

  q|Q)
    echo "  Goodbye."
    echo ""
    exit 0
    ;;

  *)
    echo "  Not a valid option. Run  bash missio.sh  again and pick a number."
    ;;

esac

echo ""
printf "  Press Enter to go back to the menu..."
read -r
exec bash missio.sh
