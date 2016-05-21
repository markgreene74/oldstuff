#!/bin/bash

directory=/foo/bar/ #CHANGE
today=$(date +'%s')
logfile=/var/log/delete_script.log
touch "$logfile"
echo $(date) >> "$logfile" # print date in logfile
echo $(df -h | grep sda) >> "$logfile" # print free disk space in logfile
# change sda to what you want to include in the log as disk space check

for entry in "$directory"/*/*
do
  if [[ -d $entry ]]; then #check if it's a directory
    howoldis=$(stat -c %Z "$entry" | cut -d " " -f 1)
    olderthan=$((today-howoldis))
    # 3 days in seconds = 259200
    # remove everything that is older than 3 days
    # keep the directories with KEEP
    if [[ $entry != *"KEEP"* ]]; then #check if contains KEEP in the filename
      if [[ $olderthan -gt 259200 ]]; then #check if it's older than 3 days
        echo "Removed" "$entry" >> "$logfile"
        rm -rf "$entry"
      else
        : #not older than 3 days do nothing
      fi
    else
      : #contains keep do nothing
    fi
  else
    : #it's a file do nothing
  fi
done
