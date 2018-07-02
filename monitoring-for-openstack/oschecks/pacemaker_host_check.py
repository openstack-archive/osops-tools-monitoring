#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Openstack Monitoring script for Sensu / Nagios
#
# Copyright © 2013-2014 eNovance <licensing@enovance.com>
#
# Author:Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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
import os
import shlex
import subprocess
import re

try:
    import utils
except ImportError:
    from oschecks import utils

def _ok_run_script(options):
    '''If there is a script to run it is executed otherwise a default message.

    Argument:
    options (Object) -- main program arguments
    '''
    if options.script:
        script = shlex.split(options.script)
        os.execvp(script[0], script)
    else:
        utils.ok("pacemaker resource %s is running"
               % options.pacemaker_resource)

def _check_resource_in_host(remaining, match_word, options, local_hostname):
    '''Searches for resource and a local_hostname on the rest of the line

    It checks if the resource is the second or third word on the line and
    search for the host on the running nodes

    Arguments:
    :param remaining:  (str)-- the rest of the line
    :param match_word: (str)-- 'Started:'-->Clone or 'Master'-->Master/Slave
    :param options:    (object)-- main program arguments
    :param local_hostname: -- localhost
    '''
    engine = re.compile('Set: ('+options.pacemaker_resource+' \[.*\]|.* \['
                +options.pacemaker_resource+'\]) '+match_word+' (\[.*?\])')
    patterns = re.search(engine, remaining)
    if patterns is not None:
        host_list = patterns.group(2).split()[1:-1]
        for host in host_list:
            if host == local_hostname:
                _ok_run_script(options)
        utils.ok(
            "pacemaker resource %s doesn't run on this node "
            "(but on %s)" % (options.pacemaker_resource, patterns.group(2))
        )

def _check_resource_in_docker_host(remaining, options, local_hostname):
    '''Searches for Docker container set resources in an active state and
    matches the local_hostname on the rest of the line

    Arguments:
    :param remaining:  (str)-- the rest of the line
    :param options:    (object)-- main program arguments
    :param local_hostname: -- localhost
    '''
    engine = re.compile('(container set: '+options.pacemaker_resource+''
                        ' \[.*\].*)')
    engine2 = re.compile('(?: Master | Slave | Started )(\S*)')
    pattern = re.search(engine, remaining)
    if pattern is not None:
        sremaining = pattern.group(1).split('):')
        for line in sremaining:
            host = re.search(engine2, line)
            if host is not None:
                if host.group(1) == local_hostname:
                    _ok_run_script(options)

def _pacemaker_host_check():
    parser = argparse.ArgumentParser(
        description='Check amqp connection of an OpenStack service.')
    parser.add_argument('-r', dest='pacemaker_resource',
                        help='pacemaker resource', required=True)
    parser.add_argument('-s', dest='script', required=False,
                        help='Script')
    parser.add_argument('--crm', dest='crm', required=False,
                        help='Use "crm_mon -1" instead of "pcs status"',
                        action='store_true', default=False)
    options = parser.parse_args()

    if options.script and (not os.path.isfile(options.script)
                      or not os.access(options.script, os.X_OK)):
        utils.critical('the script %s could not be read' % options.script)

    local_hostname = subprocess.check_output(['hostname', '-s']).strip()
    try:
        if options.crm :
            p = subprocess.Popen(['crm_mon', '-1'], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            output, error = p.communicate()
        else:
            p = subprocess.Popen(['pcs', 'status'], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            output, error = p.communicate()
        if p.returncode !=0:
            if options.crm:
                utils.critical('pcs status with status {}: {}'
                               .format(p.returncode, output.strip()))
            else:
                utils.critical('pcs status with status {}: {}'
                               .format(p.returncode, error.strip()))
    except OSError:
        utils.critical('pcs not found')

    for line in re.sub("\n  +", " ", output).splitlines():
        line = " ".join(line.strip().split())  # Sanitize separator
        if not line:
            continue
        resource, remaining = line.split(None, 1)
        if resource == options.pacemaker_resource:
            agent, __, remaining = remaining.partition(' ')
            if ' ' in remaining:
                status, __, current_hostname = remaining.partition(' ')
            else:
                status, current_hostname = remaining, ''
            if status != "Started":
                utils.critical("pacemaker resource %s is not started (%s)" %
                               (resource, status))
            if current_hostname != local_hostname:
                utils.ok("pacemaker resource %s doesn't run on this node "
                         "(but on %s)" % (resource, current_hostname))
            _ok_run_script(options)
        elif resource == 'Clone' :
            _check_resource_in_host(remaining, 'Started:', options,
                                    local_hostname)
        elif resource == 'Docker':
            _check_resource_in_docker_host(remaining, options,
                                    local_hostname)
        elif resource == 'Master/Slave':
            _check_resource_in_host(remaining, 'Masters:', options,
                                    local_hostname)

    else:
        utils.critical('pacemaker resource %s not found' %
                       options.pacemaker_resource)

def pacemaker_host_check():
    utils.safe_run(_pacemaker_host_check)
