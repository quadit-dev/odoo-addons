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
from openerp.addons.connector.unit.mapper import mapping
from openerp.addons.connector_prestashop.models.product_image.common import ProductImageAdapter
from openerp.addons.connector_prestashop_catalog_manager.models.product_image.exporter import ProductImageExportMapper

from ..backend import prestashop_1_7


@prestashop_1_7
class ProductImageAdapterExtension(ProductImageAdapter):
    _model_name = 'prestashop.product.image'

    def create(self, attributes=None):
        res = super(ProductImageAdapterExtension, self).create(attributes)
        return res['prestashop']['image']['id']

    def write(self, id, attributes=None):
        res = super(ProductImageAdapterExtension, self).write(id, attributes)
        return res['prestashop']['image']['id']


@prestashop_1_7
class ProductImageExportMapperExtension(ProductImageExportMapper):
    _model_name = 'prestashop.product.image'

    @mapping
    def filename(self, record):
        file_name = record.filename
        if not file_name:
            file_name = self._get_file_name(record)
        return {'filename': file_name}
