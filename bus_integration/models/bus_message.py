# -*- coding: utf8 -*-
#
#    Copyright (C) 2019 NDP Systèmes (<http://www.ndp-systemes.fr>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import json
from openerp import models, fields, api
from openerp.addons.connector.session import ConnectorSession
from ..connector.jobs import job_send_response


class BusMessage(models.Model):
    _name = 'bus.message'
    _order = 'create_date DESC'

    #  batch serial id
    id_serial = fields.Char(string=u"Serial ID")
    configuration_id = fields.Many2one('bus.configuration', string=u"Backend")
    date_done = fields.Datetime(u"Date Done")
    header_param_ids = fields.One2many('bus.message.header.param', 'message_id', u"Header parameters")
    message = fields.Text(u"Message")
    type = fields.Selection([('received', u"Received"), ('sent', u"Sent")], u"Message Type", required=True)
    treatment = fields.Selection([('SYNCHRONIZATION', u"Synchronization request"),
                                  ('DEPENDENCY_SYNCHRONIZATION', u"Dependency response"),
                                  ('DEPENDENCY_DEMAND_SYNCHRONIZATION', u"Dependency request"),
                                  ('SYNCHRONIZATION_RETURN', u"Synchronization response"),
                                  ('DELETION_SYNCHRONIZATION', u"Deletion request"),
                                  ('DELETION_SYNCHRONIZATION_RETURN', u"Deletion response"),
                                  ('CHECK_SYNCHRONIZATION', u"Check request"),
                                  ('CHECK_SYNCHRONIZATION_RETURN', u"Check response"),
                                  ], u"Treatment", required=True)
    state = fields.Selection([('reception', u"Recetion"),
                              ('send', u"Send"),
                              ('error', u"Error"),
                              ('warning', u"Warning")], string=u"State")
    log_ids = fields.One2many('bus.message.log', 'message_id', string=u"Logs")

    # enable to identify a message across all the databases (mother/bus/child)
    # to know witch request is targeted by witch response
    cross_id_origin_base = fields.Char("origin base")
    cross_id_origin_id = fields.Integer("origin base message id")
    cross_id_origin_parent_id = fields.Integer("origin base message parent id")

    # computed / related fields
    cross_id_str = fields.Text("cross ID", compute="_compute_cross_id_str", readonly=True)
    body = fields.Text(u"body", compute="_compute_message_fields", readonly=True)
    body_root_pretty_print = fields.Text(u"Body root", compute="_compute_message_fields", readonly=True)
    body_dependencies_pretty_print = fields.Text(u"Body dependencies", compute="_compute_message_fields", readonly=True)
    body_models = fields.Text(u"Models", compute="_compute_message_fields", readonly=True)
    extra_content = fields.Text(u"Extra-content", compute="_compute_message_fields", readonly=True)

    @api.multi
    def _compute_cross_id_str(self):
        for rec in self:
            if rec.cross_id_origin_parent_id:
                rec.cross_id_str = "{0:s}:{1:d}>{0:s}:{2:d}".format(rec.cross_id_origin_base,
                                                                    rec.cross_id_origin_parent_id,
                                                                    rec.cross_id_origin_id)
            else:
                rec.cross_id_str = "{0:s}:{1:d}".format(rec.cross_id_origin_base, rec.cross_id_origin_id)

    @api.multi
    def _compute_message_fields(self):
        for rec in self:
            try:
                message_dict = json.loads(rec.message)
                extra_content_dict = {key: message_dict[key] for key in message_dict if key not in ['body', 'header']}
                rec.extra_content = json.dumps(extra_content_dict)

                body_dict = message_dict.get('body')
                rec.body = json.dumps(body_dict)
                rec.body_root_pretty_print = json.dumps({'body': body_dict}, indent=4)
                rec.body_dependencies_pretty_print = json.dumps({'dependency': body_dict.get('dependency', {})},
                                                                indent=4)

                if 'demand' in body_dict.keys():
                    models_dict = body_dict.get('demand')
                elif 'result' in body_dict.get('return', {}).keys():
                    models_dict = body_dict.get('return').get('result')
                else:
                    models_dict = body_dict.get('root')
                models_result = []
                for model in models_dict.keys():
                    models_result.append(str(model))
                rec.body_models = ', '.join(models_result)
            except ValueError:
                rec.body = rec.message
                rec.body_root_pretty_print = rec.message
                rec.extra_content = ""
                rec.body_models = ""

    @api.multi
    def name_get(self):
        return [(rec.id, u"Message %s on %s" % (rec.type, rec.create_date)) for rec in self]

    @api.model
    def create_message(self, message_dict, type_sent_or_received, configuration):
        # message_dict is a JSON loaded dict.
        if not message_dict:
            message_dict = {}

        message = self.create({
            'type': type_sent_or_received,
            'treatment': message_dict.get('header', {}).get('treatment'),
            'id_serial': message_dict.get('header', {}).get('serial_id'),
            'configuration_id': configuration.id,
        })

        header_dict = message_dict.get('header', {})

        cross_id_origin_base = header_dict.get('cross_id_origin_base', configuration.sender_id.bus_username)
        cross_id_origin_id = header_dict.get('cross_id_origin_id', message.id)
        cross_id_origin_parent_id = header_dict.get('cross_id_origin_parent_id', False)

        message_dict['header']['cross_id_origin_base'] = cross_id_origin_base
        message_dict['header']['cross_id_origin_id'] = cross_id_origin_id
        message_dict['header']['cross_id_origin_parent_id'] = cross_id_origin_parent_id

        message.write({
            'message': json.dumps(message_dict),
            'cross_id_origin_base': cross_id_origin_base,
            'cross_id_origin_id': cross_id_origin_id,
            'cross_id_origin_parent_id': cross_id_origin_parent_id,
        })

        for key, value in message_dict.get('header', {}).iteritems():
            if key == 'treatment' or key == 'serial_id':
                continue
            self.env['bus.message.header.param'].create({
                'message_id': message.id,
                'name': key,
                'value': value,
            })
        return message

    @api.model
    def create(self, vals):
        if vals.get('done'):
            vals['date_done'] = fields.Datetime.now()
        return super(BusMessage, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('done'):
            vals['date_done'] = fields.Datetime.now()
        return super(BusMessage, self).write(vals)

    @api.multi
    def get_linked_messages(self):
        """
        :param message: response or request to find its children or parents
        :return: messages with the same cross id (origin, parent_id and id) without the message param
        """
        self.ensure_one()
        return self.search([('cross_id_origin_base', '=', self.cross_id_origin_base),
                            ('cross_id_origin_parent_id', '=', self.cross_id_origin_parent_id),
                            ('cross_id_origin_id', '=', self.cross_id_origin_id),
                            ('id', '!=', self.id)])

    @api.multi
    def get_parent(self):
        """
        :param message: received or sent message to find parent's received/sent message
        :return: messages with the same cross id (origin, parent_id and id) without the message param
        """
        self.ensure_one()
        if not self.cross_id_origin_parent_id:
            return False
        return self.search([('cross_id_origin_base', '=', self.cross_id_origin_base),
                            ('cross_id_origin_id', '=', self.cross_id_origin_parent_id),
                            ('type', '=', self.type)])

    @api.multi
    def send(self, msg_content_dict):
        self.ensure_one()
        job_send_response.delay(ConnectorSession.from_env(self.env), 'bus.configuration',
                                self.configuration_id.id, json.dumps(msg_content_dict))


class BusMessageHearderParam(models.Model):
    _name = 'bus.message.header.param'

    message_id = fields.Many2one('bus.message', u"Message", required=True)
    name = fields.Char(u"Key", required=True)
    value = fields.Char(u"Value")