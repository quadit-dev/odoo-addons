# -*- coding: utf8 -*-
#
# Copyright (C) 2020 NDP Systèmes (<http://www.ndp-systemes.fr>).
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
from odoo import models, fields, api


class ChooseDeliveryPackageEasyPackaging(models.TransientModel):
    _inherit = 'choose.delivery.package'

    carrier_id = fields.Many2one('delivery.carrier', string="Produit transporteur")


class StockPickingTypeEasyPackaging(models.Model):
    _inherit = 'stock.picking.type'

    need_easy_packaging = fields.Boolean("Mise en colis simplifiée")
    need_dest_package = fields.Boolean("Colis de destination obligatoire")


class StockPickingEasyPackaging(models.Model):
    _inherit = 'stock.picking'

    need_packaging = fields.Boolean("A besoin d'une mise en colis", compute='_compute_need_packaging')
    need_easy_packaging = fields.Boolean("Mise en colis simplifiée", related='picking_type_id.need_easy_packaging')
    need_dest_package = fields.Boolean("Colis de destination obligatoire", related='picking_type_id.need_dest_package')

    @api.multi
    def _compute_need_packaging(self):
        for rec in self:
            rec.need_packaging = rec.need_dest_package and all(
                not sm_line.result_package_id for sm_line in rec.move_line_ids_without_package)

    @api.multi
    def put_in_pack(self):
        """
        Deux boutons :
        - Tous dans un colis.
        - Multi-colis.
        """
        if not self.env.context.get('multi_pack'):
            self.move_line_ids_without_package.fill_qty_done()
        return super(StockPickingEasyPackaging, self.with_context(default_carrier_id=self.carrier_id.id)).put_in_pack()


class StockMoveLineEasyPackaging(models.Model):
    _inherit = 'stock.move.line'

    @api.multi
    def fill_qty_done(self):
        for rec in self:
            rec.qty_done = rec.product_qty