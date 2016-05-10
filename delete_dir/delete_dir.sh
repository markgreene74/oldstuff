#!/bin/bash

directory=/foo/bar #CHANGE THIS
today=$(date +'%s')

for entry in "$directory"/*
do
  if [[ -d $entry ]]; then #check if it's a directory
    howoldis=$(stat -c %Z "$entry" | cut -d " " -f 1)
    olderthan=$((today-howoldis))
    # 3 days in seconds = 259200
    # remove everything that is older than 3 days
    # keep the directories with KEEP
    if [[ $entry != *"KEEP"* ]]; then #check if contains KEEP in the directoryname
      if [[ $olderthan -gt 259200 ]]; then #check if it's older than 3 days
        echo "Remove" "$entry"
        #rm -rf "$entry"
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
