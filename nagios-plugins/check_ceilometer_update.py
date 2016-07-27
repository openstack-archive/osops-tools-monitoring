#!/usr/bin/env python
# pylint: disable=import-error,too-few-public-methods
"""
Check ceilometer has recent data
"""

from ceilometerclient import client
import datetime
import argparse
import sys
import iso8601
import pytz

NAGIOS_OK = 0
NAGIOS_WARNING = 1
NAGIOS_CRITICAL = 2
NAGIOS_UNKNOWN = 3

class CeilometerConnect(object):
    """
    Ceilometer connection class
    """
    def __init__(self, args):
        version = '2'
        self.ceilo_connect = client.get_client(version,
                                               os_username=args.username,
                                               os_password=args.password,
                                               os_tenant_name=args.tenant_name,
                                               os_auth_url=args.auth_url)

    def check_samples(self):
        """
        Check meters are incrementing
        """
        # Get last sample
        sample = self.ceilo_connect.samples.list(meter_name='cpu', limit='1')
        if sample:
            return sample[0].recorded_at
        else:
            return False

def utcnow():
    """
    Return timezone aware UTC date
    """
    return datetime.datetime.now(tz=pytz.utc)

def get_args():
    """
    Parse CLI arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username', required=True)
    parser.add_argument('-p', '--password', required=True)
    parser.add_argument('-t', '--tenant_name', required=True)
    parser.add_argument('-a', '--auth_url', required=True)
    parser.add_argument('-w', '--warn', type=int, required=True)
    parser.add_argument('-c', '--crit', type=int, required=True)
    args = parser.parse_args()
    return args

def main():
    """
    Main script body
    """
    args = get_args()

    ceilo_connect = CeilometerConnect(args)
    sample = ceilo_connect.check_samples()

    if sample:
        delta = utcnow() - iso8601.parse_date(sample)
        if delta >= datetime.timedelta(minutes=args.crit):
            print "CRITICAL: Ceilometer data behind by %s" % delta
            sys.exit(NAGIOS_CRITICAL)
        elif delta >= datetime.timedelta(minutes=args.warn):
            print "WARNING: Ceilometer data behind by %s" % delta
            sys.exit(NAGIOS_WARNING)
        else:
            print "OK: Ceilometer data updating - last updated at %s" % sample
            sys.exit(NAGIOS_OK)
    else:
        print "UNKNOWN: Ceilometer data not returning"
        sys.exit(NAGIOS_UNKNOWN)

if __name__ == "__main__":
    main()
