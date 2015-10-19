#!/bin/bash

source ~/openrc

keystone token-get 2>&1 > /dev/null
if [ $? == 0 ]; then
    echo "OK - Got a Keystone token."
    exit 0
else
    echo "CRITICAL - Unable to get a Keystone token."
    exit 2
fi
