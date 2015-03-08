#!/bin/bash
# Uses sudo, so an entry in /etc/sudoers is most likely required.

sudo virsh list 2>&1 > /dev/null
if [ $? -eq 1 ]; then
  echo "CRITICAL - problem with libvirt"
  exit 3
else
  vms=$(sudo virsh list | grep instance | wc -l)
  echo "OK - ${vms} running"
  exit 0
fi
