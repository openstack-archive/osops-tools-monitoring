#!/bin/bash

x=$(/usr/bin/curl -s https://${1}:8080/healthcheck)
if [ "${x}" == "OK" ]; then
  echo "OK - Swift Proxy healthcheck is reporting ${x}"
  exit 0
else
  echo "CRITICAL - Swift Proxy healthcheck is reporting ${x}"
  exit 3
fi
