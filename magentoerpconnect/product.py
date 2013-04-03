# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier, David Beal
#    Copyright 2013 Camptocamp SA
#    Copyright 2013 Akretion
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
import urllib2
import base64
from operator import itemgetter
import magento as magentolib
from openerp.osv import orm, fields
from openerp.addons.connector.unit.synchronizer import ImportSynchronizer
from openerp.addons.connector.exception import (MappingError,
                                                InvalidDataError)
from openerp.addons.connector.unit.mapper import (mapping,
                                                  ImportMapper
                                                  )
from .unit.backend_adapter import GenericAdapter
from .unit.import_synchronizer import (DelayedBatchImport,
                                       MagentoImportSynchronizer,
                                       TranslationImporter,
                                       )
from .backend import magento

_logger = logging.getLogger(__name__)


class magento_product_product(orm.Model):
    _name = 'magento.product.product'
    _inherit = 'magento.binding'
    _inherits = {'product.product': 'openerp_id'}

    def product_type_get(self, cr, uid, context=None):
        return [
            ('simple', 'Simple Product'),
            # XXX activate when supported
            # ('grouped', 'Grouped Product'),
            # ('configurable', 'Configurable Product'),
            # ('virtual', 'Virtual Product'),
            # ('bundle', 'Bundle Product'),
            # ('downloadable', 'Downloadable Product'),
        ]

    def _product_type_get(self, cr, uid, context=None):
        return self.product_type_get(cr, uid, context=context)

    _columns = {
        'openerp_id': fields.many2one('product.product',
                                      string='Product',
                                      required=True,
                                      ondelete='restrict'),
        # XXX website_ids can be computed from categories
        'website_ids': fields.many2many('magento.website',
                                        string='Websites',
                                        readonly=True),
        'created_at': fields.date('Created At (on Magento)'),
        'updated_at': fields.date('Updated At (on Magento)'),
        'product_type': fields.selection(_product_type_get,
                                         'Magento Product Type',
                                         required=True),
        'manage_stock': fields.selection(
            [('use_default', 'Use Default Config'),
             ('no', 'Do Not Manage Stock'),
             ('yes', 'Manage Stock')],
            string='Manage Stock Level',
            required=True),
        'manage_stock_shortage': fields.selection(
            [('use_default', 'Use Default Config'),
             ('no', 'No Sell'),
             ('yes', 'Sell Quantity < 0'),
             ('yes-and-notification', 'Sell Quantity < 0 and Use Customer Notification')],
            string='Manage Inventory Shortage',
            required=True),
        }

    _defaults = {
        'product_type': 'simple',
        'manage_stock': 'use_default',
        'manage_stock_shortage': 'use_default',
        }

    _sql_constraints = [
        ('magento_uniq', 'unique(backend_id, magento_id)',
         "A product with the same ID on Magento already exists")
    ]


class product_product(orm.Model):
    _inherit = 'product.product'

    _columns = {
        'magento_bind_ids': fields.one2many(
            'magento.product.product',
            'openerp_id',
            string='Magento Bindings',),
    }


@magento
class ProductProductAdapter(GenericAdapter):
    _model_name = 'magento.product.product'
    _magento_model = 'catalog_product'

    def search(self, filters=None, from_date=None):
        """ Search records according to some criterias
        and returns a list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}
        if from_date is not None:
            filters['updated_at'] = {'from': from_date.strftime('%Y/%m/%d %H:%M:%S')}
        with magentolib.API(self.magento.location,
                            self.magento.username,
                            self.magento.password) as api:
            # TODO add a search entry point on the Magento API
            return [int(row['product_id']) for row
                    in api.call('%s.list' % self._magento_model,
                                [filters] if filters else [{}])]
        return []

    def read(self, id, storeview_id=None, attributes=None):
        """ Returns the information of a record

        :rtype: dict
        """
        with magentolib.API(self.magento.location,
                            self.magento.username,
                            self.magento.password) as api:
            return api.call('%s.info' % self._magento_model,
                            [id, storeview_id, attributes, 'id'])
        return {}

    def get_images(self, id, storeview_id=None):
        with magentolib.API(self.magento.location,
                            self.magento.username,
                            self.magento.password) as api:
            return api.call('product_media.list', [id, storeview_id, 'id'])
        return []

    def read_image(self, id, image_name, storeview_id=None):
        with magentolib.API(self.magento.location,
                            self.magento.username,
                            self.magento.password) as api:
            return api.call('product_media.info', [id, image_name, storeview_id, 'id'])
        return {}


@magento
class ProductBatchImport(DelayedBatchImport):
    """ Import the Magento Products.

    For every product category in the list, a delayed job is created.
    Import from a date
    """
    _model_name = ['magento.product.product']

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        record_ids = self.backend_adapter.search(filters, from_date)
        _logger.info('search for magento products %s returned %s',
                     filters, record_ids)
        for record_id in record_ids:
            self._import_record(record_id)


@magento
class CatalogImageImporter(ImportSynchronizer):
    """ Import images for a record.

    Usually called from importers, in ``_after_import``.
    For instance from the products importer.
    """

    _model_name = ['magento.product.product',
                   ]

    def _get_images(self, storeview_id=None):
        return self.backend_adapter.get_images(self.magento_id, storeview_id)

    def _get_main_image_data(self, images):
        if not images:
            return {}
        # search if we have a base image defined
        image = next((img for img in images if 'base' in img['types']),
                     None)
        if image is None:
            # take the first image by priority
            images = sorted(images, key=itemgetter('position'))
            image = images[0]
        return image

    def _get_binary_image(self, image_data):
        url = image_data['url']
        binary = urllib2.urlopen(url)
        return binary.read()

    def run(self, magento_id, openerp_id):
        self.magento_id = magento_id
        images = self._get_images()
        main_image_data = self._get_main_image_data(images)
        if not main_image_data:
            return
        binary = self._get_binary_image(main_image_data)
        self.session.write(self.model._name,
                           openerp_id,
                           {'image': base64.b64encode(binary)})


@magento
class ProductImport(MagentoImportSynchronizer):
    _model_name = ['magento.product.product']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.magento_record
        # import related categories
        binder = self.get_binder_for_model('magento.product.category')
        for mag_category_id in record['categories']:
            if binder.to_openerp(mag_category_id) is None:
                importer = self.get_connector_unit_for_model(
                    MagentoImportSynchronizer,
                    model='magento.product.category')
                importer.run(mag_category_id)

    def _validate_product_type(self, data):
        """ Check if the product type is in the selection (so we can
        prevent the `except_orm` and display a better error message).
        """
        sess = self.session
        product_type = data['product_type']
        cr, uid, context = sess.cr, sess.uid, sess.context
        product_obj = sess.pool['magento.product.product']
        types = product_obj.product_type_get(cr, uid, context=context)
        available_types = [typ[0] for typ in types]
        if product_type not in available_types:
            raise InvalidDataError("The product type '%s' is not "
                                   "yet supported in the connector." %
                                   product_type)

    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``_create`` or
        ``_update`` if some fields are missing or invalid

        Raise `InvalidDataError`
        """
        self._validate_product_type(data)

    def _after_import(self, openerp_id):
        """ Hook called at the end of the import """
        translation_importer = self.get_connector_unit_for_model(
            TranslationImporter, self.model._name)
        translation_importer.run(self.magento_id, openerp_id)
        image_importer = self.get_connector_unit_for_model(
            CatalogImageImporter, self.model._name)
        image_importer.run(self.magento_id, openerp_id)


@magento
class ProductImportMapper(ImportMapper):
    _model_name = 'magento.product.product'
    #TODO :     categ, special_price => minimal_price
    direct = [('name', 'name'),
              ('description', 'description'),
              ('weight', 'weight'),
              ('price', 'list_price'),
              ('cost', 'standard_price'),
              ('short_description', 'description_sale'),
              ('sku', 'default_code'),
              ('type_id', 'product_type'),
              ('created_at', 'created_at'),
              ('updated_at', 'updated_at'),
              ]

    @mapping
    def type(self, record):
        if record['type_id'] == 'simple':
            return {'type': 'product'}
        return

    @mapping
    def website_ids(self, record):
        website_ids = []
        for mag_website_id in record['websites']:
            binder = self.get_binder_for_model('magento.website')
            website_id = binder.to_openerp(mag_website_id)
            website_ids.append(website_id)
        return {'website_ids': website_ids}

    @mapping
    def categories(self, record):
        mag_categories = record['categories']
        binder = self.get_binder_for_model('magento.product.category')

        category_ids = []
        main_categ_id = None

        for mag_category_id in mag_categories:
            cat_id = binder.to_openerp(mag_category_id, unwrap=True)
            if cat_id is None:
                raise MappingError("The product category with "
                                   "magento id %s is not imported." %
                                   mag_category_id)

            category_ids.append(cat_id)

        if category_ids:
            main_categ_id = category_ids.pop(0)

        if main_categ_id is None:
            default_categ = self.backend_record.default_category_id
            if default_categ:
                main_categ_id = default_categ.id

        result = {'categ_ids': [(6, 0, category_ids)]}
        if main_categ_id:  # OpenERP assign 'All Products' if not specified
            result['categ_id'] = main_categ_id
        return result

    @mapping
    def magento_id(self, record):
        return {'magento_id': record['product_id']}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}
