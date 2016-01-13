#!/usr/bin/env python
# -*- encoding: utf-8 -*-
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

from oschecks import utils
import json


def _check_keystone_api():
    keystone = utils.Keystone()

    def check_token():
        try:
            result = json.loads(keystone.run())
            if type(result) is dict:
                return result['id']
            elif type(result) is list:
                # We may have a cliff tab output instead of cliff.
                for row in result:
                    if row['Field'] == 'id':
                        return row['Value']
        except ValueError:
            return ''
        # Nothing found.
        return ''

    elapsed, token = utils.timeit(check_token)
    if not token:
        utils.critical("Unable to get a token")

    if elapsed > 10:
        utils.warning("Got a token after 10 seconds, it's too long."
                      "|response_time=%s" % elapsed)
    else:
        utils.ok("Got a token, Keystone API is working."
                 "|response_time=%s" % elapsed)


def check_keystone_api():
    utils.safe_run(_check_keystone_api)
