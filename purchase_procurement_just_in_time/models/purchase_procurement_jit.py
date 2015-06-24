# -*- coding: utf8 -*-
#
# Copyright (C) 2014 NDP Systèmes (<http://www.ndp-systemes.fr>).
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

from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
from openerp import fields, models, api, _, exceptions


class PurchaseOrderJustInTime(models.Model):
    _inherit = 'purchase.order'

    order_line = fields.One2many(states={'done': [('readonly', True)]})

    @api.multi
    def _create_stock_moves_improved(self, order, order_lines, group_id=False, picking_id=False):

        """
        Replaces the function _create_stock_moves of class purchase.order when executing function create (see lower).
        :param order: purchase.order
        :param order_lines: recordset of purchase.order.lines
        :param group_id: id of procurement.group
        :param picking_id: id of stock.picking
        """

        self.ensure_one()
        todo_moves = []
        if not group_id:
            group = self.env['procurement.group'].create({'name': order.name, 'partner_id': order.partner_id.id})
            group_id = group.id

        for order_line in order_lines:
            if not order_line.product_id:
                continue

            if order_line.product_id.type in ('product', 'consu'):
                for vals in self._prepare_order_line_move(order, order_line, picking_id, group_id):
                    move = self.env['stock.move'].create(vals)
                    todo_moves.append(move)
        todo_moves.action_confirm()
        todo_moves.force_assign()

    @api.multi
    def renumerate_lines(self):
        for rec in self:
            number = 10
            for line in rec.order_line:
                line.line_no = str(number)
                number += 10

    @api.multi
    def do_merge(self):
        result = super(PurchaseOrderJustInTime, self).do_merge()
        assert len(result.keys()) == 1, "Error: multiple children purchase orders in do_merge result"
        assert isinstance(result.keys()[0], int), "Error, type is not integer: wrong value for id"
        children_po = self.env['purchase.order'].browse(result.keys()[0])
        children_po.renumerate_lines()
        return result



class PurchaseOrderLineJustInTime(models.Model):
    _inherit = 'purchase.order.line'

    line_no = fields.Char("Line no.")
    ack_ref = fields.Char("Acknowledge Reference", help="Reference of the supplier's last reply to confirm the delivery"
                                                        " at the planned date")
    date_ack = fields.Date("Last Acknowledge Date",
                           helps="Last date at which the supplier confirmed the delivery at the planned date.")
    opmsg_type = fields.Selection([('no_msg', "Ok"), ('late', "LATE"), ('early', "EARLY"), ('reduce', "REDUCE"),
                        ('to_cancel', "CANCEL")], compute="_compute_opmsg", string="Message Type")
    opmsg_delay = fields.Integer("Message Delay", compute="_compute_opmsg")
    opmsg_reduce_qty = fields.Float("New target quantity after procurement cancellation", readonly=True, default=False)
    opmsg_text = fields.Char("Operational message", compute="_compute_opmsg_text", help="This field holds the "
                                                        "operational messages generated by the system to the operator")
    remaining_qty = fields.Float("Remaining quantity", help="Quantity not yet delivered by the supplier",
                                 compute="_get_remaining_qty", store=False)
    to_delete = fields.Boolean('True if all the procurements of the purchase order line are canceled')
    father_line_id = fields.Many2one('purchase.order.line', string="Very first line splited", readonly=True)
    children_line_ids = fields.One2many('purchase.order.line', 'father_line_id', string="Children lines")
    children_number = fields.Integer(string="Number of children", readonly=True, compute='_compute_children_number')
    location_id = fields.Many2one(related='order_id.location_id')

    @api.depends('date_planned', 'date_required', 'to_delete', 'product_qty', 'opmsg_reduce_qty')
    def _compute_opmsg(self):

        """
        Sets parameters date_planned, date_required, and opmsg_type.
        """

        for rec in self:
            if rec.date_planned and rec.date_required:
                date_planned = datetime.strptime(rec.date_planned, DEFAULT_SERVER_DATE_FORMAT)
                date_required = datetime.strptime(rec.date_required, DEFAULT_SERVER_DATE_FORMAT)
                min_late_days = int(self.env['ir.config_parameter'].get_param(
                                                            "purchase_procurement_just_in_time.opmsg_min_late_delay"))
                min_early_days = int(self.env['ir.config_parameter'].get_param(
                                                            "purchase_procurement_just_in_time.opmsg_min_early_delay"))
                if date_planned >= date_required:
                    delta = date_planned - date_required
                    if delta.days >= min_late_days:
                        rec.opmsg_type = 'late'
                        rec.opmsg_delay = delta.days
                else:
                    delta = date_required - date_planned
                    if delta.days >= min_early_days:
                        rec.opmsg_type = 'early'
                        rec.opmsg_delay = delta.days
            if rec.to_delete and rec.product_qty != 0:
                rec.opmsg_type = 'to_cancel'
            if not rec.to_delete and rec.opmsg_reduce_qty and rec.opmsg_reduce_qty < rec.product_qty:
                rec.opmsg_type = 'reduce'

    @api.depends('opmsg_type', 'opmsg_delay', 'opmsg_reduce_qty', 'product_qty', 'to_delete', 'state')
    def _compute_opmsg_text(self):

        """
        Sets parameters opmsg_type, opmsg_delay, opmsg_reduce_qty, product_qty, to_delete and state.
        """

        for rec in self:
            msg = ""
            if rec.to_delete and rec.product_qty != 0:
                msg += _("CANCEL LINE")
            if not rec.to_delete and rec.opmsg_reduce_qty and rec.opmsg_reduce_qty < rec.product_qty:
                msg += _("REDUCE QTY to %.1f %s ") % (rec.opmsg_reduce_qty, rec.product_uom.name)
            if rec.opmsg_type == 'early':
                msg += _("EARLY by %i day(s)") % rec.opmsg_delay
            elif rec.opmsg_type == 'late':
                msg += _("LATE by %i day(s)") % rec.opmsg_delay
            rec.opmsg_text = msg

    @api.multi
    def open_form_purchase_order_line(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.line',
            'name': _("Purchase Order Line: %s") % self.line_no,
            'views': [(False, "form")],
            'res_id': self.id,
            'context': {}
        }


    @api.depends('move_ids.product_qty')
    def _get_remaining_qty(self):

        """
        Calculates ramaining_qty
        """

        for rec in self:
            do_calculation = True
            for move in rec.move_ids:
                if move.product_uom != rec.product_uom:
                    do_calculation = False
                    break
            if do_calculation:
                delivered_qty = sum([move.product_uom_qty for move in rec.move_ids if move.state == 'done'])
                rec.remaining_qty = rec.product_qty - delivered_qty

    @api.depends('children_line_ids')
    def _compute_children_number(self):

        """
        Calculates children_number
        """
        for rec in self:
            rec.children_number = len(rec.children_line_ids)

    @api.model
    def create(self, vals):

        """
        Improves original function create. Sets automatically a line number and creates appropriate moves in a picking.
        :return: the same result as original create function
        """

        maximum = 0
        if not vals.get('line_no', False):
            list_line_no = []
            list_no = []
            order = self.env['purchase.order'].browse(vals['order_id'])
            for line in order.order_line:
                list_no += [line.line_no]
            for item in [l.line_no for l in order.order_line]:
                try:
                    list_line_no.append(int(item))
                except ValueError:
                    pass
            theo_value = 10*(1 + len(self.env['purchase.order'].browse(vals['order_id']).order_line))
            if list_line_no:
                maximum = max(list_line_no)
            if maximum >= theo_value or theo_value in list_line_no:
                theo_value = maximum + 10
            vals['line_no'] = str(theo_value)
        result = super(PurchaseOrderLineJustInTime, self).create(vals)
        if result.order_id.state not in ['draft', 'done', 'cancel']:
            list_lines = [x for x in result.order_id.order_line if x != result]
            if list_lines:
                result.order_id.set_order_line_status(list_lines[0].state)
                group = False
                for line in list_lines:
                    for move in line.move_ids:
                        if move.state not in ['done', 'cancel']:
                            group = move.group_id
                            break
            result.order_id.set_order_line_status('confirmed')
            if result.product_qty != 0 and not result.move_ids:
                result.order_id._create_stock_moves_improved(result.order_id, result, group_id=group.id)
        return result

    @api.multi
    def copy_name_and_set_parent(self, vals):

        """
        Copy a line and sets the parameters father_line_id and line_no to the good values.
        :return: the new line
        """

        new_line = self.copy(vals)
        if not self.father_line_id:
            new_line.father_line_id = self
        new_line.line_no = new_line.father_line_id.line_no + ' - ' + str(new_line.father_line_id.children_number)
        return new_line

    @api.multi
    def change_qty_or_create(self, qty, global_qty_ordered):

        """
        Used to increase quantity of a purchase order line : see comments in function update_moves.
        """

        diff = qty - global_qty_ordered
        move_without_proc_id = [x for x in self.move_ids if not x.procurement_id]
        move_with_proc_id = [x for x in self.move_ids if x.procurement_id]
        if len(move_without_proc_id + move_with_proc_id) != 0:
            if len(move_without_proc_id) == 0:
                new_move = move_with_proc_id[0].copy({'product_uom_qty': diff, 'procurement_id': False,
                                                      'purchase_line_id': self.id})
                new_move.purchase_line_id = self.id
                new_move.action_confirm()
                new_move.action_assign()
            else:
                move = move_without_proc_id[0]
                move.product_uom_qty = move.product_uom_qty + diff
        else:
            self.order_id._create_stock_moves_improved(self.order_id, self)

    @api.multi
    def delete_cancel_create(self, qty):

        """
        Used to decrease quantity of a purchase order line : see comments in function update_moves.
        """

        moves_without_proc_id = self.move_ids.filtered(lambda m: m.state != 'done' and not
                                                    m.procurement_id).sorted(key=lambda m: m.product_qty, reverse=True)
        moves_with_proc_id = self.move_ids.filtered(lambda m: m.state != 'done' and m.procurement_id).\
                                                                    sorted(key=lambda m: m.product_qty, reverse=True)
        move_list = moves_without_proc_id + moves_with_proc_id
        if len(moves_without_proc_id + moves_with_proc_id) != 0:
            _sum = sum([x.product_uom_qty for x in self.move_ids if x.state != 'cancel'])
            while _sum > qty:
                if len(move_list) > 0:
                    if move_list[0].product_uom_qty > _sum - qty:
                        move_list[0].product_uom_qty -= _sum - qty
                        if move_list[0].procurement_id:
                            _sum = qty
                        else:
                            _sum -= _sum - qty
                    else:
                        if move_list[0].procurement_id:
                            _sum -= move_list[0].product_uom_qty
                            move_list[0].product_uom_qty = 0.0
                        else:
                            move_list[0].with_context({'cancel_procurement': True}).action_cancel()
                            _sum -= move_list[0].product_uom_qty
                        move_list -= move_list[0]
            if _sum < qty:
                diff = qty - _sum
                if not moves_without_proc_id:
                    new_move = moves_with_proc_id[0].copy({'product_uom_qty': diff, 'procurement_id': False,
                                                           'purchase_line_id': self.id})
                    new_move.action_confirm()
                    new_move.action_assign()
                else:
                    moves_without_proc_id[0] += diff

    @api.multi
    def update_moves(self, vals):

        """
        Updates moves associated to a purchase order line, based on the procurement order associated to this line.
        When increasing quantity: if any move is linked with no procurement, we increase its quantity. If not, we
        create a new move.
        When decreasing a quantity, we progressively delete the moves linked with no procurements, then cancel the other
        ones until the global quantity ordered is lower or equal to the new quantity. Then, if it is lower, we create a
        new move as before, to reach the appropriate quantity.
        """

        self.ensure_one()
        global_qty_ordered = sum(x.product_uom_qty for x in self.move_ids if x.state != 'cancel')
        if self.state == 'confirmed':
            if vals['product_qty'] == 0:
                for move in self.move_ids:
                    move.with_context({'cancel_procurement': True}).action_cancel()
            if vals['product_qty'] > 0:
                if vals.get('product_qty') > global_qty_ordered:
                    self.change_qty_or_create(vals.get('product_qty'), global_qty_ordered)
                if vals.get('product_qty') < global_qty_ordered:
                    self.delete_cancel_create(vals.get('product_qty'))
            move_to_remove = [x for x in self.move_ids if x.state == 'cancel']
            for move in move_to_remove:
                move.purchase_line_id = False
            order = self.order_id
            if len(self.move_ids) == 0:
                self.action_cancel()
            if len(order.order_line) == 0:
                order.action_cancel()

    @api.multi
    def write(self, vals):

        """
        Improves the original write function. Allows to update moves of a purchase order line even if it is confirmed.
        :return: the same result as original write function
        """

        result = super(PurchaseOrderLineJustInTime, self).write(vals)
        if vals.get('product_qty'):
            if vals['product_qty'] < sum([x.product_uom_qty for x in self.move_ids if x.state == 'done']):
                raise exceptions.except_orm(_('Error!'), _("Impossible to cancel moves at state done."))
            for item in self:
                item.update_moves(vals)
        return result


class ProcurementOrderPurchaseJustInTime(models.Model):
    _inherit = 'procurement.order'

    @api.model
    def propagate_cancel(self, procurement):

        """
        Improves the original propagate_cancel function. If the corresponding purchase order is draft, it eventually
        cancels and/or deletes tho purchase order line and the purchase order.
        """

        result = None
        qty = 0
        if procurement.rule_id.action == 'buy' and procurement.purchase_line_id:
            if procurement.purchase_line_id.state not in ['draft', 'cancel']:
                qty = procurement.purchase_line_id.product_qty
            try:
                result = super(ProcurementOrderPurchaseJustInTime, self).propagate_cancel(procurement)
            except exceptions.except_orm:
                # Canceling a confirmed procurement order
                if procurement.purchase_line_id.state not in ['draft', 'cancel']:
                    procurement.purchase_line_id.product_qty = qty
                    total_need = sum([x.product_qty for x in procurement.purchase_line_id.procurement_ids
                                                                        if x.state != 'cancel' and x != procurement])
                    if total_need != 0:
                        total_need = self.with_context({'cancelling_active_proc': True}).\
                                                                                    _calc_new_qty_price(procurement)[0]
                    procurement.purchase_line_id.opmsg_reduce_qty = total_need
                    if total_need == 0:
                        procurement.purchase_line_id.to_delete = True
                    procurement.purchase_line_id.product_qty = qty
        # Checking what should be cancelled
        qty = False
        if procurement.purchase_line_id and procurement.purchase_line_id.order_id.state != 'draft':
            qty = procurement.purchase_line_id.product_qty
        if procurement.purchase_line_id and procurement.purchase_line_id.order_id.state == 'draft':
            # in this case, purchase order is not yet confirmed
            line = procurement.purchase_line_id
            order = line.order_id
            global_qty = 0
            for order_line in order.order_line:
                global_qty += sum([x.product_qty for x in order_line.procurement_ids if x.product_id == line.product_id
                                   and x != procurement and x.state != 'cancel'])
            if line.state == 'draft' and global_qty == 0:
                line.unlink()
            if not order.order_line:
                order.unlink()
        if qty:
            procurement.purchase_line_id.product_qty = qty
        return result


class SplitLine(models.TransientModel):
    _name = 'split.line'
    _description = "Split Line"

    def get_pol(self):
        return self.env['purchase.order.line'].browse(self.env.context.get('active_id'))

    line_id = fields.Many2one('purchase.order.line', string="Direct parent line in purchase order", default=get_pol,
                              required=True, readonly=True)
    qty = fields.Float(string="New quantity of direct parent line")

    @api.multi
    def _check_split_possible(self):

        """
        Raises error if it is impossible to split the purchase order line.
        """

        self.ensure_one()
        if self.env.context.get('active_ids') and len(self.env.context.get('active_ids')) > 1:
            raise exceptions.except_orm(_('Error!'), _("Please split lines one by one"))
        else:
            if self.qty <= 0:
                raise exceptions.except_orm(_('Error!'), _("Impossible to split a negative or null quantity"))
            if self.line_id.state not in ['draft', 'confirmed']:
                raise exceptions.except_orm(_('Error!'), _("Impossible to split line which is not in state draft or "
                                                    "confirmed"))
            if self.line_id.state == 'draft':
                if self.qty >= self.line_id.product_qty:
                    raise exceptions.except_orm(_('Error!'), _("Please choose a lower quantity to split"))
        if self.line_id.state == 'confirmed':
            _sum = sum(x.product_uom_qty for x in self.line_id.move_ids if x.state == 'done')
            if self.qty < _sum:
                raise exceptions.except_orm(_('Error!'), _("Impossible to split a move in state done"))
            if self.qty >= sum([m.product_uom_qty for m in self.line_id.move_ids if m.state != 'cancel']):
                raise exceptions.except_orm(_('Error!'), _("Please choose a lower quantity to split"))

    @api.multi
    def do_split(self):

        """
        Separates a purchase order line into two ones.
        """

        self._check_split_possible()
        if self.line_id.state == 'draft':
            diff = self.line_id.product_qty - self.qty
            self.line_id.product_qty = self.qty
            self.line_id.copy_name_and_set_parent({'product_qty': diff})
        if self.line_id.state == 'confirmed':
            list_moves = self.line_id.move_ids.filtered(lambda m: m.state not in ['draft', 'done', 'cancel']).\
                                                                                sorted(key=lambda m: m.product_qty)
            _sum = sum(x.product_uom_qty for x in self.line_id.move_ids if x.state == 'done')
            moves_to_keep = []
            move_to_split = False
            if _sum != self.qty:
                for move in list_moves:
                    _sum += move.product_uom_qty
                    if _sum > self.qty:
                        move_to_split = move
                        break
                    if _sum == self.qty:
                        moves_to_keep += [move]
                        break
                    else:
                        moves_to_keep += [move]
            new_pol = self.line_id.copy_name_and_set_parent({'product_qty': 0, 'move_ids': False, 'children_line_ids':
                                                                self.env['purchase.order.line'], 'children_number': 0})
            for move in self.line_id.move_ids:
                if move not in moves_to_keep and move != move_to_split and move.state not in ['done', 'cancel']:
                    move.purchase_line_id = new_pol
            if move_to_split:
                self.env['stock.move'].split(move_to_split, self.qty - sum([m.product_uom_qty for m in moves_to_keep]))
                move_to_split.purchase_line_id = new_pol
            new_pol.product_qty = sum(x.product_uom_qty for x in new_pol.move_ids)
            self.line_id.product_qty = sum([x.product_uom_qty for x in self.line_id.move_ids])
            for move in self.line_id.move_ids:
                if move.purchase_line_id and move.state != 'assigned':
                    move.action_assign()
            self.line_id.order_id.set_order_line_status(self.line_id.state)
