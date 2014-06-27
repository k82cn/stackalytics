# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import time

import six

from stackalytics.openstack.common import log as logging
from stackalytics.processor import utils


LOG = logging.getLogger(__name__)

NAME_AND_DATE_PATTERN = r'<h3>(?P<member_name>[^<]*)[\s\S]*?' \
                        r'<div class="span-7 last">(?P<date_joined>[^<]*)'
COMPANY_PATTERN = r'<strong>Date\sJoined[\s\S]*?<b>(?P<company_draft>[^<]*)' \
                  r'[\s\S]*?From\s(?P<date_from>[\s\S]*?)\(Current\)'

CNT_EMPTY_MEMBERS = 50


def _convert_str_fields_to_unicode(result):
    for field, value in six.iteritems(result):
        if type(value) is str:
            try:
                value = six.text_type(value, 'utf8')
                result[field] = value
            except Exception:
                pass


def _retrieve_member(uri, member_id, html_parser):

    content = utils.read_uri(uri)

    if not content:
        return {}

    member = {}

    for rec in re.finditer(NAME_AND_DATE_PATTERN, content):
        result = rec.groupdict()

        member['member_id'] = member_id
        member['member_name'] = result['member_name']
        member['date_joined'] = result['date_joined']
        member['member_uri'] = uri
        break

    member['company_draft'] = '*independent'
    for rec in re.finditer(COMPANY_PATTERN, content):
        result = rec.groupdict()

        member['company_draft'] = html_parser.unescape(result['company_draft'])

    return member


def log(uri, runtime_storage_inst, days_to_update_members):
    LOG.debug('Retrieving new openstack.org members')

    last_update_members_date = runtime_storage_inst.get_by_key(
        'last_update_members_date') or 0
    last_member_index = runtime_storage_inst.get_by_key(
        'last_member_index') or 0

    end_update_date = int(time.time()) - days_to_update_members * 24 * 60 * 60

    if last_update_members_date <= end_update_date:
        last_member_index = 0
        last_update_members_date = int(time.time())

        runtime_storage_inst.set_by_key('last_update_members_date',
                                        last_update_members_date)

    cnt_empty = 0
    cur_index = last_member_index + 1
    html_parser = six.moves.html_parser.HTMLParser()

    while cnt_empty < CNT_EMPTY_MEMBERS:

        profile_uri = uri + str(cur_index)
        member = _retrieve_member(profile_uri, str(cur_index), html_parser)

        if 'member_name' not in member:
            cnt_empty += 1
            cur_index += 1
            continue

        _convert_str_fields_to_unicode(member)

        cnt_empty = 0
        last_member_index = cur_index
        cur_index += 1
        LOG.debug('New member: %s', member['member_id'])
        yield member

    LOG.debug('Last_member_index: %s', last_member_index)
    runtime_storage_inst.set_by_key('last_member_index', last_member_index)
