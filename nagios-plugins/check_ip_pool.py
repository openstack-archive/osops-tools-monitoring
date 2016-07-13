#!/usr/bin/env python
"""
Check for remaining IP addresses
"""
# pylint: disable=import-error

from neutronclient.v2_0 import client
from ipaddress import ip_network
import sys
import argparse

NAGIOS_OK = 0
NAGIOS_WARNING = 1
NAGIOS_CRITICAL = 2
NAGIOS_UNKNOWN = 3

def main():
    """
    Main script body
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username', required=True)
    parser.add_argument('-p', '--password', required=True)
    parser.add_argument('-t', '--tenant_name', required=True)
    parser.add_argument('-a', '--auth_url', required=True)
    parser.add_argument('-w', '--warn', type=int, required=True)
    parser.add_argument('-c', '--critical', type=int, required=True)
    args = parser.parse_args()

    neutron = client.Client(username=args.username, password=args.password,
                            tenant_name=args.tenant_name,
                            auth_url=args.auth_url)
    neutron.format = 'json'

    for arg in [args.warn, args.critical]:
        if not 0 <= arg <= 100:
            print "Alert parameters must be valid percentages"
            sys.exit(NAGIOS_UNKNOWN)

    # Get external network
    # Assume a single external network for the minute
    ext_net = [net for net in neutron.list_networks()['networks']
               if net['router:external']]

    total_addresses = 0
    for subnet in neutron.show_network(ext_net[0]['id'])['network']['subnets']:
        total_addresses += ip_network(neutron.show_subnet(subnet)
                                      ['subnet']['cidr']).num_addresses

    floating_ips = len(neutron.list_floatingips()['floatingips'])
    router_ips = len([router for router in neutron.list_routers()['routers']
                      if router['external_gateway_info']])

    total_used = floating_ips + router_ips

    percentage_used = 100 * total_used/total_addresses

    if percentage_used >= args.warn:
        code = NAGIOS_WARNING
        msg = 'WARNING'
    elif percentage_used >= args.critical:
        code = NAGIOS_CRITICAL
        msg = 'CRITICAL'
    else:
        code = NAGIOS_OK
        msg = 'OK'

    print '{0}: {1}% of IP pool used, '\
            '{2} out of {5} addresses in use | '\
            'total_used={2};{3};{4};;{5} '\
            'total_available={5} '\
            'floating_ips_used={6} '\
            'ext_routers_used={7}'\
            .format(msg, percentage_used, total_used,
                    (total_addresses * args.warn)/100,
                    (total_addresses * args.critical)/100,
                    total_addresses, floating_ips, router_ips)
    sys.exit(code)

if __name__ == "__main__":
    main()
