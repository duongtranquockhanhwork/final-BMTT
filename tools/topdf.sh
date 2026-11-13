#!/bin/zsh
# usage: topdf.sh in.docx out.pdf
osascript <<OSA
tell application "Pages"
  set theDoc to open (POSIX file "$1")
  delay 2
  export theDoc to (POSIX file "$2") as PDF
  close theDoc saving no
end tell
OSA
