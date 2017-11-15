#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Openstack Monitoring script for Sensu / Nagios
#
# Copyright © 2013-2014 eNovance <licensing@enovance.com>
#
# Authors: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
#          Sofer Athlan-Guyot <sofer.athlan@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import argparse
import datetime
import logging
import os
import re
import urlparse

from keystoneclient.v2_0 import client
from neutronclient.neutron import client as neutron

from oschecks import utils


def _check_neutron_api():
    neutron = utils.Neutron()
    neutron.add_argument('-w', dest='warning', type=int, default=5,
                         help='Warning timeout for neutron APIs calls')
    neutron.add_argument('-c', dest='critical', type=int, default=10,
                         help='Critical timeout for neutron APIs calls')
    options, args, client = neutron.setup()

    def network_list():
        try:
            return client.list_networks()
        except Exception as ex:
            utils.critical(str(ex))

    elapsed, networks = utils.timeit(network_list)
    if not networks or len(networks.get('networks', [])) <= 0:
        utils.critical("Unable to contact neutron API.")

    if elapsed > options.critical:
        utils.critical("Get networks took more than %d seconds, "
                       "it's too long.|response_time=%d" %
                       (options.critical, elapsed))
    elif elapsed > options.warning:
        utils.warning("Get networks took more than %d seconds, "
                      "it's too long.|response_time=%d" %
                      (options.warning, elapsed))
    else:
        utils.ok("Get networks, neutron API is working: "
                 "list %d networks in %d seconds.|response_time=%d" %
                 (len(networks['networks']), elapsed, elapsed))


def check_neutron_api():
    utils.safe_run(_check_neutron_api)


class NeutronUtils(object):
    DAEMON_DEFAULT_PORT = 9696

    def __init__(self, client, tenant_id):
        self.client = client
        self.msgs = []
        self.start = self.totimestamp()
        self.notifications = ["floatingip_creation_time=%s" % self.start]
        self.connection_done = False
        self.all_floating_ips = []
        self.fip = None
        self.network_id = None
        self.tenant_id = tenant_id

    # python has no "toepoch" method: http://bugs.python.org/issue2736
    # now, after checking http://stackoverflow.com/a/16307378,
    # and http://stackoverflow.com/a/8778548 made my mind to this approach
    @staticmethod
    def totimestamp(dt=None, epoch=datetime.datetime(1970, 1, 1)):
        if not dt:
            dt = datetime.datetime.utcnow()
        td = dt - epoch
        # return td.total_seconds()
        return int((td.microseconds +
                   (td.seconds + td.days * 24 * 3600) * 10**6) / 1e6)

    def check_connection(self, force=False):
        if not self.connection_done or force:
            try:
                # force a connection to the server
                self.connection_done = self.client.list_ports()
            except Exception as e:
                utils.critical("Cannot connect to neutron: %s\n" % e)

    def mangle_url(self, url):
        # This first connection populate the structure we need inside
        # the object.  This does not cost anything if a connection has
        # already been made.
        self.check_connection()
        try:
            endpoint_url = urlparse.urlparse(url)
        except Exception as e:
            utils.unknown("you must provide an endpoint_url in the form"
                          "<scheme>://<url>/ (%s)" % e)
        scheme = endpoint_url.scheme
        if scheme is None:
            utils.unknown("you must provide an endpoint_url in the form"
                          "<scheme>://<url>/ (%s)" % e)
        catalog_url = None
        try:
            catalog_url = urlparse.urlparse(
                self.client.httpclient.endpoint_url)
        except Exception as e:
            utils.unknown("unknown error parsing the catalog url : %s" % e)

        port = endpoint_url.port
        if port is None:
            if catalog_url.port is None:
                port = self.DAEMON_DEFAULT_PORT
            else:
                port = catalog_url.port

        netloc = "%s:%i" % (endpoint_url.hostname, port)
        url = urlparse.urlunparse([scheme,
                                   netloc,
                                   catalog_url.path,
                                   catalog_url.params,
                                   catalog_url.query,
                                   catalog_url.fragment])
        self.client.httpclient.endpoint_override = url

    def get_duration(self):
        return self.totimestamp() - self.start

    def list_floating_ips(self):
        if not self.all_floating_ips:
            for floating_ip in self.client.list_floatingips(
                    fields=['floating_ip_address', 'id'],
                    tenant_id=self.tenant_id)['floatingips']:
                self.all_floating_ips.append(floating_ip)
        return self.all_floating_ips

    def check_existing_floatingip(self, floating_ip=None, delete=False):
        count = 0
        found_ips = []
        for ip in self.list_floating_ips():
            if floating_ip == 'all' or floating_ip.match(
                    ip['floating_ip_address']):
                if delete:
                    # asynchronous call, we do not check that it worked
                    self.client.delete_floatingip(ip['id'])
                found_ips.append(ip['floating_ip_address'])
                count += 1
        if count > 0:
            if delete:
                self.notifications.append("Found %d ip(s): %s" %
                                          (count, '{' + ', '.join(
                                           found_ips) + '}'))
            else:
                self.msgs.append("Found %d ip(s): %s. " %
                                 (count, ', '.join(found_ips)) +
                                 "Won't create test floating ip. "
                                 "Please check and delete.")

    def get_network_id(self, ext_network_name):
        if not self.msgs:
            if not self.network_id:
                try:
                    self.network_id = self.client.list_networks(
                        name=ext_network_name, fields='id')['networks'][0]['id']
                except Exception:
                    self.msgs.append("Cannot find ext network named '%s'."
                                     % ext_network_name)

    def create_floating_ip(self):
        if not self.msgs:
            try:
                body = {'floatingip': {'floating_network_id': self.network_id}}
                self.fip = self.client.create_floatingip(body=body)
                self.notifications.append(
                    "fip=%s" % self.fip['floatingip']['floating_ip_address'])
            except Exception as e:
                self.msgs.append("Cannot create a floating ip: %s" % e)

    def delete_floating_ip(self):
        if not self.msgs:
            try:
                self.client.delete_floatingip(
                    self.fip['floatingip']['id'])
            except Exception:
                self.msgs.append("Cannot remove floating ip %s"
                                 % self.fip['floatingip']['id'])


def fip_type(string):
    if string == 'all':
        return 'all'
    else:
        return re.compile(string)


def _check_neutron_floating_ip():
    neutron = utils.Neutron()
    neutron.add_argument('--endpoint_url', metavar='endpoint_url', type=str,
                            help='Override the catalog endpoint.')
    neutron.add_argument('--force_delete', action='store_true',
                            help=('If matching floating ip are found, delete '
                                'them and add a notification in the message '
                                'instead of getting out in critical state.'))
    neutron.add_argument('--floating_ip', metavar='floating_ip', type=fip_type,
                            default=None,
                            help=('Regex of IP(s) to check for existance. '
                                'This value can be "all" for conveniance '
                                '(match all ip). This permit to avoid certain '
                                'floating ip to be kept. Its default value '
                                'prevents the removal of any existing '
                                'floating ip'))
    neutron.add_argument('--ext_network_name', metavar='ext_network_name',
                            type=str, default='public',
                            help=('Name of the "public" external network '
                            '(public by default)'))
    options, args, client = neutron.setup()

    project = (options.os_project_id if options.os_project_id else
                options.os_project_name)
    tenant = (options.os_tenant_id if options.os_tenant_id else
                options.os_tenant_name)
    util = NeutronUtils(client, tenant or project)

    # Initiate the first connection and catch error.
    util.check_connection()

    if options.endpoint_url:
        util.mangle_url(options.endpoint_url)
        # after mangling the url, the endpoint has changed.  Check that
        # it's valid.
        util.check_connection(force=True)

    if options.floating_ip:
        util.check_existing_floatingip(options.floating_ip,
                                       options.force_delete)
    util.get_network_id(options.ext_network_name)
    util.create_floating_ip()
    util.delete_floating_ip()

    if util.msgs:
        utils.critical(", ".join(util.msgs))

    duration = util.get_duration()
    notification = ""

    if util.notifications:
        notification = "(" + ", ".join(util.notifications) + ")"

    utils.ok("Floating ip created and deleted %s| time=%d"
             % (notification, duration))


def check_neutron_floating_ip():
    utils.safe_run(_check_neutron_floating_ip)
