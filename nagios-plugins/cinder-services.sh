#!/bin/bash

source ~/openrc

output=$(cinder service-list | grep down)
if [ $? -eq 0 ]; then
  echo -n "CRITICAL - OpenStack Cinder services down: "
  echo "${output}" | awk '{print $2,$4}' | while read LINE; do
    echo -n "${LINE}; "
  done
  echo ""
  exit 2
else
  echo "OK - All nodes up"
  exit 0
fi
