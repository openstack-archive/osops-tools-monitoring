#!/bin/bash

source ~/openrc

# The login URL to access horizon.
# Example: http://example.com/auth/login/
HORIZON_URL="${1}"

# If you don't use regions, this will generally be OPENSTACK_KEYSTONE_URL in local_settings.py.
# View the source on the Horizon page for more information and search for "region".
REGION="${2}"

curl -sL -c /tmp/cookie.txt -b /tmp/cookie.txt $1 -o /dev/null
CSRF_TOKEN=$(grep csrftoken /tmp/cookie.txt | awk '{print $NF}')

TIMEOUT_CHECK=$(curl -sL -b /tmp/cookie.txt -d "username=${OS_USERNAME}" -d "password=${OS_PASSWORD}" -d "region=${REGION}" -d "csrfmiddlewaretoken=${CSRF_TOKEN}" -m 20 --referer ${HORIZON_URL}               ${HORIZON_URL} | tee /tmp/horizon.txt)
LOGIN_CHECK=$(grep alert-error /tmp/horizon.txt)

rm /tmp/cookie.txt
rm /tmp/horizon.txt

if [ "${TIMEOUT_CHECK}" == "" ] || [ "${LOGIN_CHECK}" != "" ]; then
    echo "CRITICAL - Horizon is inaccessible"
    exit 2
fi

echo "Horizon Login OK"
exit 0
