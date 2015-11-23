#
# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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
import subprocess
import unittest


class TestScripts(unittest.TestCase):
    SCRIPTS = [
        'amqp',
        'ceilometer_api',
        'ceph_df',
        'ceph_health',
        'cinder_api',
        'cinder_volume',
        'glance_api',
        'glance_image_exists',
        'glance_upload',
        'keystone_api',
        'neutron_api',
        'neutron_floating_ip',
        'nova_api',
        'nova_instance',
    ]


for script in TestScripts.SCRIPTS:
    def test_check_script(self):
        proc = subprocess.Popen("oschecks-check_" + script)
        proc.wait()
        self.assertEqual(2, proc.returncode)
    setattr(TestScripts, "test_script_check_" + script, test_check_script)
