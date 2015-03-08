#!/bin/bash

source ~/openrc

if [ -z "${1}" ]; then
  image="CirrOS"
else
  image="${1}"
fi

glance image-list | grep -q "${image}"

if [ $? == 0 ]; then
  echo "OK - Glance is working."
  exit 0
else
  echo "CRITICAL - Glance is not working."
  exit 2
fi
