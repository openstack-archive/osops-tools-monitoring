#!/usr/bin/env python
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

try:
    import utils
except ImportError:
    from oschecks import utils

def _ok_run_script(options):
   '''
     If there is a script to run it is executed
     otherwise a default message
   '''
   if options.script is not None:
      script = shlex.split(options.script)
      os.execvp(script[0], script)
   else:
      utils.ok("pacemaker resource %s is running" % options.pacemaker_resource)

def _check_resource_in_host(remaining,running_type,options,local_hostname):
   '''
      This function checks if the resource is the second or third word on the line and
      search for the host on the running nodes
      remaining = the rest of the line
      running_type =  'Started:' is its a Clone of 'Master' is its a Master/Slave resource
      options = the arguments of the function
      local_hostname
   '''
   words = remaining.split()
   if words[1] == options.pacemaker_resource or words[2][1:-1] == options.pacemaker_resource:
      try:
         start = words.index(running_type)+1
         end = start+words[start:].index(']')
         for host in words[start:end]:
            if  host == local_hostname :
               _ok_run_script(options)
         utils.ok("pacemaker resource %s doesn't on this node"
                   "(but on %s)" % (options.pacemaker_resource, str(words[start+1:end])))
      except Exception as e:
         utils.critical('pacemaker resource %s not started' %
               options.pacemaker_resource)

def _pacemaker_host_check():
    parser = argparse.ArgumentParser(
        description='Check amqp connection of an OpenStack service.')
    parser.add_argument('-r', dest='pacemaker_resource',
                        help='pacemaker resource', required=True)
    parser.add_argument('-s', dest='script', required=False,
                        help='Script')
    parser.add_argument('--crm',dest='crm',required=False,
                        help='Use "crm_mon -1" instead of "pcs status"',
                        action='store_true', default=False)
    options = parser.parse_args()
    '''
     First thing after parsed the arguments
     it checks whether is a script file and whether it exits
    '''
    try:
        if options.script is not None:
            file=open(options.script)
            file.close()
    except IOError:
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

    for line in output.replace("\n     "," ").splitlines():
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
            _check_resource_in_host(remaining,'Started:',options,local_hostname)
        elif resource == 'Master/Slave':
             _check_resource_in_host(remaining,'Masters:',options,local_hostname) 

    else:
        utils.critical('pacemaker resource %s not found' %
                       options.pacemaker_resource)


def pacemaker_host_check():
    utils.safe_run(_pacemaker_host_check)
