# -*- coding: utf8 -*-
#
#    Copyright (C) 2020 NDP Systèmes (<http://www.ndp-systemes.fr>).
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

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    function_selection = fields.Many2one('res.partner.function', string='Job')

    @api.multi
    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if 'function_selection' in vals:
            function = self.env['res.partner.function'].browse(vals.get('function_selection'))
            self.function = function.name
        return res

    @api.model_create_single
    def create(self, vals):
        res = super(ResPartner, self).create(vals)
        if 'function_selection' in vals:
            function = self.env['res.partner.function'].browse(vals.get('function_selection'))
            res.function = function.name
        return res
