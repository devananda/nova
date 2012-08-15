# Copyright (c) 2012 NTT DOCOMO, INC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Baremetal DB utils for test."""

from nova import context as nova_context
from nova import flags
from nova import test
from nova.tests.baremetal import utils


flags.DECLARE('baremetal_sql_connection',
              'nova.virt.baremetal.db.sqlalchemy.session')


class BMDBTestCase(test.TestCase):

    def setUp(self):
        super(BMDBTestCase, self).setUp()
        self.flags(baremetal_sql_connection='sqlite:///:memory:')
        utils.clear_tables()
        self.context = nova_context.get_admin_context()
