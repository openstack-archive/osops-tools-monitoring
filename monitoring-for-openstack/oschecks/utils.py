#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Openstack Monitoring script for Sensu / Nagios
#
# Copyright © 2013-2014 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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


import copy
import itertools
import os
import sys
import time
import traceback

import psutil

AMQP_PORT = 5672


def unknown(msg):
    print("UNKNOWN: %s" % msg)
    sys.exit(3)


def critical(msg):
    print("CRITICAL: %s" % msg)
    sys.exit(2)


def warning(msg):
    print("WARNING: %s" % msg)
    sys.exit(1)


def ok(msg):
    print("OK: %s" % msg)
    sys.exit(0)


def check_process_name(name, p):
    try:
        len(p.cmdline)
    except TypeError:
        pname = p.name()
        pcmdline = p.cmdline()
    else:
        pname = p.name
        pcmdline = p.cmdline

    if pname == name:
        return True
    # name can be truncated and a script so check also if it can be an
    # argument to an interpreter
    if len(pcmdline) > 0 and os.path.basename(pcmdline[0]) == name:
        return True
    if len(pcmdline) > 1 and os.path.basename(pcmdline[1]) == name:
        return True
    return False


def check_process_exists_and_amqp_connected(name):
    processes = filter(lambda p: check_process_name(name, p),
                       psutil.process_iter())
    if not processes:
        critical("%s is not running" % name)
    for p in processes:
        try:
            conn_func = getattr(p, 'get_connections', p.connections)
            connections = conn_func(kind='inet')
        except psutil.NoSuchProcess:
            continue
        found_amqp = (
            len(list(itertools.takewhile(lambda c:
                len(getattr(c, 'remote_address', c.raddr)) <= 1 or
                getattr(c, 'remote_address', c.raddr)[1] != AMQP_PORT,
                connections))) != len(connections))
        if found_amqp:
            ok("%s is working." % name)
    critical("%s is not connected to AMQP" % name)


def check_process_exists(name):
    processes = filter(lambda p: check_process_name(name, p),
                       psutil.process_iter())
    if not processes:
        critical("%s is not running" % name)
    ok("%s is working." % name)


def timeit_wrapper(func):
    def wrapper(*arg, **kw):
        t1 = time.time()
        res = func(*arg, **kw)
        t2 = time.time()
        return (t2 - t1), res
    return wrapper


@timeit_wrapper
def timeit(func, *args, **kwargs):
    return func(*args, **kwargs)


def safe_run(method):
    try:
        method()
    except Exception:
        critical(traceback.format_exc())


class Nova(object):
    def __init__(self):
        from novaclient import shell
        self.nova = shell.OpenStackComputeShell()
        self.base_argv = copy.deepcopy(sys.argv[1:])
        self.nova.parser = self.nova.get_base_parser(self.base_argv)
        self.add_argument = self.nova.parser.add_argument

    def setup(self, api_version='2.1'):
        from novaclient.client import Client
        (options, args) = self.nova.parser.parse_known_args(self.base_argv)
        if options.help:
            options.command = None
            self.nova.do_help(options)
            sys.exit(2)
        auth_token = getattr(args, 'os_token', None)
        api_version = (
            getattr(options, 'os_compute_api_version', api_version) or
            api_version
        )
        try:
            nova_client = Client(
                api_version,
                username=options.os_username,
                password=options.os_password,
                project_name=getattr(
                    options, 'os_project_name', getattr(
                        options, 'os_tenant_name', None
                    )
                ),
                project_id=getattr(
                    options, 'os_project_id', getattr(
                        options, 'os_tenant_id', None
                    )
                ),
                auth_token=auth_token,
                auth_url=options.os_auth_url,
                region_name=options.os_region_name,
                cacert=options.os_cacert,
                insecure=options.insecure,
                timeout=options.timeout)
        except Exception as ex:
            critical(ex)
        return options, args, nova_client


class Glance(object):
    def __init__(self):
        from glanceclient import shell
        self.glance = shell.OpenStackImagesShell()
        self.base_argv = copy.deepcopy(sys.argv[1:])
        self.glance.parser = self.glance.get_base_parser(sys.argv)
        self.add_argument = self.glance.parser.add_argument

    def setup(self, api_version=2):
        (options, args) = self.glance.parser.parse_known_args(self.base_argv)
        if options.help:
            options.command = None
            self.glance.do_help(options)
            sys.exit(2)
        api_version = (
            getattr(options, 'os_image_api_version', api_version) or
            api_version
        )
        try:
            client = self.glance._get_versioned_client(api_version, options)
        except Exception as ex:
            critical(ex)
        return options, args, client


class Ceilometer(object):
    def __init__(self):
        from ceilometerclient import shell
        self.ceilometer = shell.CeilometerShell()
        self.base_argv = copy.deepcopy(sys.argv[1:])
        self.ceilometer.parser = self.ceilometer.get_base_parser()
        self.add_argument = self.ceilometer.parser.add_argument

    def setup(self, api_version=2):
        from ceilometerclient import client
        (options, args) = self.ceilometer.parser.parse_known_args(
            self.base_argv)
        if options.help:
            options.command = None
            self.ceilometer.do_help(options)
            sys.exit(2)
        client_kwargs = vars(options)
        try:
            return options, client.get_client(api_version, **client_kwargs)
        except Exception as ex:
            critical(ex)


class Cinder(object):
    def __init__(self):
        from cinderclient import shell
        self.cinder = shell.OpenStackCinderShell()
        self.base_argv = copy.deepcopy(sys.argv[1:])
        self.cinder.parser = self.cinder.get_base_parser()
        self.add_argument = self.cinder.parser.add_argument

    def setup(self, api_version='1'):
        from cinderclient import client
        (options, args) = self.cinder.parser.parse_known_args(self.base_argv)
        if options.help:
            options.command = None
            self.cinder.do_help(options)
            sys.exit(2)
        if options.os_volume_api_version:
            api_version = options.os_volume_api_version
        try:
            client = client.get_client_class(api_version)(
                options.os_username,
                options.os_password,
                tenant_name=getattr(
                    options, 'os_project_name', getattr(
                        options, 'os_tenant_name', None
                    )
                ),
                tenant_id=getattr(
                    options, 'os_project_id', getattr(
                        options, 'os_tenant_id', None
                    )
                ),
                auth_url=options.os_auth_url,
                region_name=options.os_region_name,
                cacert=options.os_cacert,
                insecure=options.insecure)
        except Exception as ex:
            critical(ex)
        return options, args, client


class Neutron(object):
    def __init__(self):
        from neutronclient import shell
        self.neutron = shell.NeutronShell('2.0')
        self.base_argv = copy.deepcopy(sys.argv[1:])
        self.neutron.parser = self.neutron.build_option_parser(
            "Neutron client", "2.0")
        self.add_argument = self.neutron.parser.add_argument

    def setup(self):
        (options, args) = self.neutron.parser.parse_known_args(self.base_argv)
        self.neutron.options = options
        self.neutron.api_version = {'network': self.neutron.api_version}
        try:
            self.neutron.authenticate_user()
            return options, args, self.neutron.client_manager.neutron
        except Exception as ex:
            critical(ex)


class Keystone(object):
    def __init__(self):
        if (sys.version_info > (3, 0)):
            # Python 3 code in this block
            from io import StringIO
        else:
            # Python 2 code in this block
            from StringIO import StringIO

        from openstackclient import shell
        self.shell = shell.OpenStackShell()
        self.shell.stdout = StringIO()
        self.shell.stderr = StringIO()
        self.help = False

    def run(self):
        command = ['token', 'issue']
        vformat = ['-f', 'value', '-c', 'id']
        if 'help' in sys.argv or '--help' in sys.argv or '-h' in sys.argv:
            rc = self.shell.run(command)
        else:
            cmd_arg = sys.argv[1:]
            # removes parameters used in vformat
            for opt in ['-f', '-c']:
                if opt in cmd_arg:
                    index = cmd_arg.index(opt)
                    if len(cmd_arg) > (index + 1):
                        for i in range(2):
                            cmd_arg.pop(index)
            rc = self.shell.run(command + cmd_arg + vformat)
        out = self.shell.stdout.getvalue()
        return rc, out
