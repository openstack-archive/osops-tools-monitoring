#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Openstack Monitoring script for Sensu / Nagios
#
# Copyright © 2012-2014 eNovance <licensing@enovance.com>
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
import time

from novaclient.client import Client  # noqa
from novaclient import exceptions
from six.moves import urllib

from oschecks import utils


def _check_nova_api():
    nova = utils.Nova()
    nova.add_argument('-w', dest='warning', type=int, default=5,
                      help='Warning timeout for nova APIs calls')
    nova.add_argument('-c', dest='critical', type=int, default=10,
                      help='Critical timeout for nova APIs calls')
    options, args, client = nova.setup()

    def flavors_list():
        try:
            return list(client.flavors.list())
        except Exception as ex:
            utils.critical(str(ex))

    elapsed, flavors = utils.timeit(flavors_list)
    if elapsed > options.critical:
        utils.critical("Get flavors took more than %d seconds, "
                       "it's too long.|response_time=%d" %
                       (options.critical, elapsed))
    elif elapsed > options.warning:
        utils.warning("Get flavors took more than %d seconds, "
                      "it's too long.|response_time=%d" %
                      (options.warning, elapsed))
    else:
        utils.ok("Get flavors, nova API is working: "
                 "list %d flavors in %d seconds.|response_time=%d" %
                 (len(flavors), elapsed, elapsed))


def check_nova_api():
    utils.safe_run(_check_nova_api)


default_image_name = 'cirros'
default_flavor_name = 'm1.tiny'
default_instance_name = 'monitoring_test'


class Novautils(object):
    def __init__(self, nova_client):
        self.nova_client = nova_client
        self.msgs = []
        self.start = self.totimestamp()
        self.notifications = ["instance_creation_time=%s" % self.start]
        self.performances = []
        self.instance = None
        self.connection_done = False

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
                self.connection_done = self.nova_client.limits.get()
            except Exception as e:
                utils.critical("Cannot connect to nova: %s\n" % e)

    def get_duration(self):
        return self.totimestamp() - self.start

    def mangle_url(self, url):
        self.check_connection()

        try:
            endpoint_url = urllib.parse.urlparse(url)
        except Exception as e:
            utils.unknown("you must provide an endpoint_url in the form"
                          "<scheme>://<url>/ (%s)\n" % e)
        scheme = endpoint_url.scheme
        if scheme is None:
            utils.unknown("you must provide an endpoint_url in the form"
                          "<scheme>://<url>/ (%s)\n" % e)
        catalog_url = None
        try:
            catalog_url = urllib.parse.urlparse(
                self.nova_client.client.management_url)
        except Exception as e:
            utils.unknown("unknown error parsing the catalog url : %s\n" % e)

        port = endpoint_url.port
        if port is None:
            if catalog_url.port is None:
                port = 8774
            else:
                port = catalog_url.port

        netloc = "%s:%i" % (endpoint_url.hostname, port)
        url = urllib.parse.urlunparse([scheme,
                                       netloc,
                                       catalog_url.path,
                                       catalog_url.params,
                                       catalog_url.query,
                                       catalog_url.fragment])
        self.nova_client.client.set_management_url(url)

    def check_existing_instance(self, instance_name, delete, timeout=45):
        count = 0
        for s in self.nova_client.servers.list():
            if s.name == instance_name:
                if delete:
                    s.delete()
                    self._instance_status(s, timeout, count)
                    self.performances.append("undeleted_server_%s_%d=%s"
                                             % (s.name, count, s.created))
                count += 1
        if count > 0:
            if delete:
                self.notifications.append("Found '%s' present %d time(s)"
                                          % (instance_name, count))
            else:
                self.msgs.append(
                    "Found '%s' present %d time(s). " %
                    (instance_name, count) +
                    "Won't create test instance. "
                    "Please check and delete.")

    def get_image(self, image_name):
        if not self.msgs:
            try:
                if hasattr(self.nova_client, 'images'):
                    self.image = self.nova_client.images.find(name=image_name)
                else:
                    self.image = self.nova_client.glance.find_image(image_name)
            except Exception as e:
                self.msgs.append("Cannot find the image %s (%s)"
                                 % (image_name, e))

    def get_flavor(self, flavor_name):
        if not self.msgs:
            try:
                self.flavor = self.nova_client.flavors.find(name=flavor_name)
            except Exception as e:
                self.msgs.append("Cannot find the flavor %s (%s)"
                                 % (flavor_name, e))

    def get_network(self, network_name):
        if self.msgs or not network_name:
            self.network = None
        elif hasattr(self.nova_client, 'networks'):
            self.network = self.nova_client.networks.find(name=image_name)
        else:
            self.network = self.nova_client.neutron.find_network(image_name)

    def create_instance(self, instance_name):
        if not self.msgs:
            kwargs = {}

            try:
                if self.network:
                    try:
                        network = self.nova_client.networks.find(
                            label=network).id
                    except exceptions.NotFound:
                        try:
                            network = self.nova_client.networks.find(
                                id=network).id
                        except exceptions.NotFound:
                            self.msgs.append("Cannot find network %s" %
                                             network)
                            return
                    kwargs['nics'] = [{'net-id': self.network}]
                self.instance = self.nova_client.servers.create(
                    name=instance_name,
                    image=self.image,
                    flavor=self.flavor, **kwargs)
            except Exception as e:
                self.msgs.append("Cannot create the vm %s (%s)"
                                 % (instance_name, e))

    def instance_ready(self, timeout):
        if not self.msgs:
            timer = 0
            while self.instance.status != "ACTIVE":
                if timer >= timeout:
                    self.msgs.append("Cannot create the vm")
                    break
                time.sleep(1)
                timer += 1
                try:
                    self.instance.get()
                except Exception as e:
                    self.msgs.append("Problem getting the status of the vm: %s"
                                     % e)
                    break

    def delete_instance(self):
        if not self.msgs or self.instance is not None:
            try:
                self.instance.delete()
            except Exception as e:
                self.msgs.append("Problem deleting the vm: %s" % e)

    def instance_deleted(self, timeout):
        deleted = False
        timer = 0
        while not deleted and not self.msgs:
            time.sleep(1)
            if timer >= timeout:
                self.msgs.append("Could not delete the vm within %d seconds"
                                 % timer)
                break
            timer += 1
            try:
                self.instance.get()
            except exceptions.NotFound:
                deleted = True
            except Exception as e:
                self.msgs.append("Cannot delete the vm (%s)" % e)
                break

    def _instance_status(self, instance, timeout, count):
        deleted = False
        timer = 0
        while not deleted:
            time.sleep(1)
            if timer >= timeout:
                self.msgs.append(
                    "Could not delete the vm %s within %d seconds " %
                    (instance.name, timer) + "(created at %s)" %
                    instance.created)
                break
            timer += 1
            try:
                instance.get()
            except exceptions.NotFound:
                deleted = True
            except Exception as e:
                self.msgs.append("Cannot delete the vm %s (%s)"
                                 % (instance.name, e))
                self.performances.append("undeleted_server_%s_%d=%s"
                                         % (instance.name,
                                            count,
                                            instance.created))
                break


def _check_nova_instance():
    nova = utils.Nova()
    nova.add_argument('--endpoint_url', metavar='endpoint_url', type=str,
                        help='Override the catalog endpoint.')

    nova.add_argument('--image_name', metavar='image_name', type=str,
                        default=default_image_name,
                        help="Image name to use (%s by default)"
                        % default_image_name)

    nova.add_argument('--flavor_name', metavar='flavor_name', type=str,
                        default=default_flavor_name,
                        help="Flavor name to use (%s by default)"
                        % default_flavor_name)

    nova.add_argument('--instance_name', metavar='instance_name', type=str,
                        default=default_instance_name,
                        help="Instance name to use (%s by default)"
                        % default_instance_name)

    nova.add_argument('--force_delete', action='store_true',
                        help='If matching instances are found delete '
                             'them and add a notification in the message'
                             ' instead of getting out in critical state.')

    nova.add_argument('--timeout_delete', metavar='timeout_delete',
                        type=int, default=45,
                        help='Max number of second to delete an existing '
                             'instance (45 by default).')

    nova.add_argument('--network', metavar='network', type=str, default=None,
                        help="Override the network name to use")

    nova.add_argument('--verbose', action='count',
                        help='Print requests on stderr.')

    options, args, nova_client = nova.setup()

    util = Novautils(nova_client)

    if options.verbose:
        ch = logging.StreamHandler()
        nova_client.client._logger.setLevel(logging.DEBUG)
        nova_client.client._logger.addHandler(ch)

    # Initiate the first connection and catch error.
    util.check_connection()

    if options.endpoint_url:
        util.mangle_url(options.endpoint_url)
        # after mangling the url, the endpoint has changed.  Check that
        # it's valid.
        util.check_connection(force=True)

    util.check_existing_instance(options.instance_name,
                                 options.force_delete,
                                 options.timeout_delete)
    util.get_image(options.image_name)
    util.get_flavor(options.flavor_name)
    util.get_network(options.network)
    util.create_instance(options.instance_name)
    util.instance_ready(options.timeout)
    util.delete_instance()
    util.instance_deleted(options.timeout)

    if util.msgs:
        utils.critical(", ".join(util.msgs))

    duration = util.get_duration()
    notification = ""
    if util.notifications:
        notification = "(" + ", ".join(util.notifications) + ")"
    performance = ""
    if util.performances:
        performance = " ".join(util.performances)
    utils.ok("Nova instance spawned and deleted in %d seconds %s| time=%d %s"
             % (duration, notification, duration, performance))


def check_nova_instance():
    utils.safe_run(_check_nova_instance)
