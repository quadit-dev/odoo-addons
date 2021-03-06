odoo.define('web_ui_stock_batch.BatchMoveLineRow', function (require) {
    "use strict";

    var Widget = require('web.Widget');
    var rpc = require('web.rpc');

    return Widget.extend({
        template: 'BatchMoveLineRow',
        init: function (batchMainList, move_line) {
            this._super(batchMainList);
            this.batchMainList = batchMainList;
            this.id = move_line.id;
            this.move_line = move_line;
            this.product = move_line.product;
            this.quantity_to_do = move_line.quantity;
            this.quantity_done = 0;
            this.display_qty = this.quantity_done + "/" + this.quantity_to_do;
        },
        start: function () {
            this._super();
        },
        renderElement: function () {
            this._super();
            console.log("ProductTableRow renderElement");
            this.$('button.js_change_location').click(ev => { this.batchMainList.allow_change_location(this) });
            this.$('button.js_confirm_location').click(ev => { this.confirm_location() });
            this.$('button.js_open_numpad').click(ev => { this.batchMainList.open_numpad(this) });
            this.$('button.js_confirm_qty').click(ev => { this.confirm_qty() });
        },
        update_location: function (location) {
            let sml_update_move_line_info_params = {
                model: 'stock.move.line',
                method: 'change_location_from_scan_batch',
                args: [[this.id], location.id],
            };
            rpc.query(sml_update_move_line_info_params)
                .then(() => {
                    this.move_line.location_name = location.name;
                    this.move_line.location_barcode = location.barcode;
                    this.$('#move_line_location').text(this.move_line.location_name);
            });
        },
        confirm_location: function () {
            this.batchMainList.forbid_change_location();
            this.batchMainList.$('#helper_location').addClass('d-none');
            this.batchMainList.show_or_hide_change_location();
            this.$('#move_line_product').addClass('font-weight-bold');
            this.$('#move_line_product').addClass('text-warning');
            this.batchMainList.$('#manual_scan_product').toggleClass('d-none');
        },
        update_num_lot: function (product_infos) {
            this.product.lot_id = product_infos.lot_id;
            this.product.lot_name = product_infos.lot_name;
            this.$('#move_line_lot').text(this.product.lot_name);
            this.$('#move_line_lot').addClass('text-success');
        },
        update_quantity: function () {
            this.quantity_done += 1;
            this.display_qty = this.quantity_done + "/" + this.quantity_to_do;
            this.check_qty();
            this.$('#move_line_quantity').text(this.display_qty);
        },
        qty_higher: function () {
            this.$('#move_line_quantity').removeClass('text-success');
            this.$('#move_line_quantity').removeClass('text-warning');
            this.$('#move_line_quantity').addClass('text-danger');
            this.$('#move_line_quantity').addClass('font-weight-bold');
            this.$('#move_line_uom').removeClass('text-success');
            this.$('#move_line_uom').removeClass('text-warning');
            this.$('#move_line_uom').addClass('text-danger');
            this.$('#move_line_uom').addClass('font-weight-bold');
            this.batchMainList.$('#confirm_qty_header').addClass('d-none');
            this.batchMainList.move_line_rows.forEach((move_line_row) => {
                move_line_row.$('#confirm_qty_body').addClass('d-none')
            });
            this.$('button.js_confirm_qty').addClass('d-none');
        },
        qty_lower: function () {
            this.$('#move_line_quantity').removeClass('text-success');
            this.$('#move_line_quantity').addClass('text-warning');
            this.$('#move_line_quantity').removeClass('text-danger');
            this.$('#move_line_quantity').addClass('font-weight-bold');
            this.$('#move_line_uom').removeClass('text-success');
            this.$('#move_line_uom').addClass('text-warning');
            this.$('#move_line_uom').removeClass('text-danger');
            this.$('#move_line_uom').addClass('font-weight-bold');
            this.batchMainList.$('#confirm_qty_header').removeClass('d-none');
            this.batchMainList.move_line_rows.forEach((move_line_row) => {
                move_line_row.$('#confirm_qty_body').removeClass('d-none')
            });
            this.$('button.js_confirm_qty').removeClass('d-none');
        },
        qty_right: function () {
            this.$('#move_line_quantity').addClass('text-success');
            this.$('#move_line_quantity').removeClass('text-warning');
            this.$('#move_line_quantity').removeClass('text-danger');
            this.$('#move_line_quantity').removeClass('font-weight-bold');
            this.$('#move_line_uom').addClass('text-success');
            this.$('#move_line_uom').removeClass('text-warning');
            this.$('#move_line_uom').removeClass('text-danger');
            this.$('#move_line_uom').removeClass('font-weight-bold');
            this.batchMainList.$('#confirm_qty_header').removeClass('d-none');
            this.batchMainList.move_line_rows.forEach((move_line_row) => {
                move_line_row.$('#confirm_qty_body').removeClass('d-none')
            });
            this.$('button.js_confirm_qty').removeClass('d-none');
        },
        check_qty: function () {
            if (this.quantity_done > this.quantity_to_do) {
                this.qty_higher();
            }
            else if (this.quantity_done < this.quantity_to_do) {
                this.qty_lower();
            }
            else if (this.quantity_done === this.quantity_to_do) {
                this.qty_right();
            }
        },
        validate_new_qty: function (numpad) {
            this.quantity_done = numpad.quantity;
            this.display_qty = this.quantity_done + "/" + this.quantity_to_do;
            this.check_qty();
            this.$('#move_line_quantity').text(this.display_qty);
            this.batchMainList.exit_numpad();
        },
        update_move_line_qty_to_do: function () {
            let sml_update_move_line_info_params = {
                model: 'stock.move.line',
                method: 'change_qty_to_do_from_scan_batch',
                args: [[this.id], this.quantity_done],
            };
            rpc.query(sml_update_move_line_info_params)
                .then(() => {
                    this.quantity_to_do = this.quantity_done;
                    this.display_qty = this.quantity_done + "/" + this.quantity_to_do;
                    this.$('#move_line_quantity').text(this.display_qty);
            })
        },
        confirm_qty: function () {
            this.batchMainList.$('#change_qty_header').addClass('d-none');
            this.batchMainList.move_line_rows.forEach((move_line_row) => {
                move_line_row.$('#change_qty_body').addClass('d-none')
            });
            this.$('button.js_open_numpad').addClass('d-none');
            this.batchMainList.$('#confirm_qty_header').addClass('d-none');
            this.batchMainList.move_line_rows.forEach((move_line_row) => {
                move_line_row.$('#change_qty_body').addClass('d-none')
            });
            this.$('button.js_confirm_qty').addClass('d-none');
            this.$('#move_line_quantity').addClass('text-success');
            this.$('#move_line_quantity').removeClass('text-warning');
            this.$('#move_line_quantity').removeClass('font-weight-bold');
            this.$('#move_line_uom').addClass('text-success');
            this.$('#move_line_uom').removeClass('text-warning');
            this.$('#move_line_uom').removeClass('font-weight-bold');
            this.$('#move_line_picking').addClass('text-warning');
            this.$('#move_line_picking').addClass('font-weight-bold');
            this.batchMainList.$('#manual_scan_product').toggleClass('d-none');
            this.batchMainList.$('#manual_scan_product').removeClass('warning-background');
            this.batchMainList.$('#manual_scan_picking').toggleClass('d-none');
            if (this.quantity_done !== this.quantity_to_do) {
                this.batchMainList.create_new_move_line(this);
                this.update_move_line_qty_to_do();
            }
        },
        send_qty_done_to_odoo: function () {
            let sml_update_odoo_qty_info_params = {
                model: 'stock.move.line',
                method: 'web_ui_update_odoo_qty_batch',
                args: [[this.move_line.id], this.quantity_done],
            };
            rpc.query(sml_update_odoo_qty_info_params);
        },
    });
});
