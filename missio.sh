#!/bin/bash

# Add Homebrew to PATH in case it's not already there (Apple Silicon)
if [[ -f /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

clear
echo ""
echo "======================================="
echo "   Missio LinkedIn Outreach Agent"
echo "======================================="
echo ""
echo "  1)  Fill my Sales Nav list           (adds ~200 leads from your search)"
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
echo "  q)  Quit"
echo ""
printf "  What would you like to do? "
read -r choice

echo ""

case "$choice" in

  1)
    echo "Opening browser to fill your Sales Navigator list..."
    echo "(This will add up to 200 leads. Run it again tomorrow to continue.)"
    echo ""
    python3 main.py populate-list --brand missio
    ;;

  2)
    echo "Generating today's messages in preview mode..."
    echo "(Nothing will be sent — just showing you what Claude would write.)"
    echo ""
    python3 main.py run --brand missio --dry-run
    ;;

  3)
    echo "Starting today's outreach session..."
    echo "(Browser will open. You can minimize it — don't close it.)"
    echo ""
    python3 main.py run --brand missio
    ;;

  4)
    python3 main.py status --brand missio
    ;;

  5)
    python3 main.py report --brand missio
    ;;

  6)
    python3 main.py report --brand missio --week
    ;;

  7)
    python3 main.py report --brand missio --save
    echo ""
    echo "Report saved to logs/reports/"
    ;;

  8)
    python3 main.py report --brand missio --week --save
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
      python3 main.py mark-booked --brand missio --url "$url" --notes "$notes"
    else
      python3 main.py mark-booked --brand missio --url "$url"
    fi
    ;;

  10)
    echo ""
    printf "  Paste the LinkedIn profile URL to add to do-not-contact: "
    read -r url
    python3 main.py mark-dnc --url "$url"
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
