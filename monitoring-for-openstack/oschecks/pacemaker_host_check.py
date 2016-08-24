!/usr/bin/env python
# -*- encoding: utf-8 -*-
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
    if options.script is not None:
        script = shlex.split(options.script)
        os.execvp(script[0], script)
    else:
        utils.ok("pacemaker resource %s is running"
               % options.pacemaker_resource)

def _check_resource_in_host(remaining, match_word, options, local_hostname):
    '''It checks if the resource is the second or third word on the line and
    search for the host on the running nodes

    Arguments:
    remaining (str)-- the rest of the line
    match_word (str)-- 'Started:'-->Clone or 'Master'-->Master/Slave resource
    options (object)-- main program arguments
    local_hostname -- localhost
    '''
    engine = re.compile('Set: ('+options.pacemaker_resource+' \[.*\]|.* \['
                +options.pacemaker_resource+'\]) '+match_word+' (\[.*?\])')
    patters = re.search(engine, remaining)
    if patters is not None:
        hostList = patters.group(2).split()[1:-1]
        for host in hostList:
            if host == local_hostname:
                _ok_run_script(options)
        utils.ok("pacemaker resource %s doesn't on this node "
                         "(but on %s)" % (resource, patters.group(2)))

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

    if options.script is not None and not os.path.isfile(options.script):
        utils.critical('the script %s could not be read' % options.script)

    local_hostname = subprocess.check_output(['hostname', '-s']).strip()
    try:
        if options.crm :
            output = subprocess.check_output(['crm_mon', '-1'])
        else:
            output = subprocess.check_output(['pcs', 'status'])
    except subprocess.CalledProcessError as e:
        utils.critical('pcs status with status %s: %s' %
                       e.returncode, e.output)
    except OSError:
        utils.critical('pcs not found')

    for line in output.replace("\n     ", " ").splitlines():
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
                utils.ok("pacemaker resource %s doesn't on this node "
                         "(but on %s)" % (resource, current_hostname))
            _ok_run_script(options)
        elif resource == 'Clone' :
            _check_resource_in_host(remaining, 'Started:', options,
                                    local_hostname)
        elif resource == 'Master/Slave':
            _check_resource_in_host(remaining, 'Masters:', options,
                                    local_hostname)

    else:
        utils.critical('pacemaker resource %s not found' %
                       options.pacemaker_resource)

def pacemaker_host_check():
    utils.safe_run(_pacemaker_host_check)

