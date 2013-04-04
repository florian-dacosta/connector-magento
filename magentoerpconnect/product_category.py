# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2013 Camptocamp SA
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
import magento as magentolib
from openerp.osv import orm, fields
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


class magento_product_category(orm.Model):
    _name = 'magento.product.category'
    _inherit = 'magento.binding'
    _inherits = {'product.category': 'openerp_id'}
    _description = 'Magento Product Category'

    _columns = {
        'openerp_id': fields.many2one('product.category',
                                      string='Product Category',
                                      required=True,
                                      ondelete='cascade'),
        'description': fields.text('Description', translate=True),
        'magento_parent_id': fields.many2one(
            'magento.product.category',
             string='Magento Parent Category',
             ondelete='cascade'),
        'magento_child_ids': fields.one2many(
            'magento.product.category',
             'magento_parent_id',
             string='Magento Child Categories'),
    }

    _sql_constraints = [
        ('magento_uniq', 'unique(backend_id, magento_id)',
         'A product category with same ID on Magento already exists.'),
    ]


class product_category(orm.Model):
    _inherit = 'product.category'

    _columns = {
        'magento_bind_ids': fields.one2many(
            'magento.product.category', 'openerp_id',
            string="Magento Bindings"),
    }


@magento
class ProductCategoryAdapter(GenericAdapter):
    _model_name = 'magento.product.category'
    _magento_model = 'catalog_category'

    def search(self, filters=None, from_date=None):
        """ Search records according to some criterias and returns a
        list of ids

        :rtype: list
        """
        if filters is None:
            filters = {}

        if from_date is not None:
            # updated_at include the created records
            filters['updated_at'] = {'from': from_date.strftime('%Y/%m/%d %H:%M:%S')}

        with magentolib.API(self.magento.location,
                            self.magento.username,
                            self.magento.password) as api:
            # the search method is on ol_customer instead of customer
            return api.call('oerp_catalog_category.search',
                            [filters] if filters else [{}])
        return []

    def read(self, id, storeview_id=None, attributes=None):
        """ Returns the information of a record

        :rtype: dict
        """
        with magentolib.API(self.magento.location,
                            self.magento.username,
                            self.magento.password) as api:
            return api.call('%s.info' % self._magento_model,
                             [id, storeview_id, attributes])
        return {}

    def tree(self, parent_id=None, storeview_id=None):
        """ Returns a tree of product categories

        :rtype: dict
        """
        def filter_ids(tree):
            children = {}
            if tree['children']:
                for node in tree['children']:
                    children.update(filter_ids(node))
            category_id = {tree['category_id']: children}
            return category_id

        with magentolib.API(self.magento.location,
                            self.magento.username,
                            self.magento.password) as api:
            tree = api.call('%s.tree' % self._magento_model, [parent_id,
                                                              storeview_id])
            return filter_ids(tree)


@magento
class ProductCategoryBatchImport(DelayedBatchImport):
    """ Import the Magento Product Categories.

    For every product category in the list, a delayed job is created.
    A priority is set on the jobs according to their level to rise the
    chance to have the top level categories imported first.
    """
    _model_name = ['magento.product.category']

    def _import_record(self, magento_id, priority=None):
        """ Delay a job for the import """
        super(ProductCategoryBatchImport, self)._import_record(
                magento_id, priority=priority)

    def run(self, filters=None):
        """ Run the synchronization """
        from_date = filters.pop('from_date', None)
        if from_date is not None:
            updated_ids = self.backend_adapter.search(filters, from_date)
        else:
            updated_ids = None

        base_priority = 10
        def import_nodes(tree, level=0):
            for node_id, children in tree.iteritems():
                # By changing the priority, the top level category has
                # more chance to be imported before the childrens.
                # However, importers have to ensure that their parent is
                # there and import it if it doesn't exist
                if updated_ids is None or node_id in updated_ids:
                    self._import_record(node_id, priority=base_priority+level)
                import_nodes(children, level=level+1)
        tree = self.backend_adapter.tree()
        import_nodes(tree)


@magento
class ProductCategoryImport(MagentoImportSynchronizer):
    _model_name = ['magento.product.category']

    def _import_dependencies(self):
        """ Import the dependencies for the record"""
        record = self.magento_record
        env = self.environment
        # import parent category
        # the root category has a 0 parent_id
        if record.get('parent_id'):
            binder = self.get_binder_for_model()
            parent_id = record['parent_id']
            if binder.to_openerp(parent_id) is None:
                importer = env.get_connector_unit(MagentoImportSynchronizer)
                importer.run(parent_id)

    def _after_import(self, openerp_id):
        """ Hook called at the end of the import """
        translation_importer = self.get_connector_unit_for_model(
                TranslationImporter, self.model._name)
        translation_importer.run(self.magento_id, openerp_id)


@magento
class ProductCategoryImportMapper(ImportMapper):
    _model_name = 'magento.product.category'

    direct = [
            ('description', 'description'),
            ]

    @mapping
    def name(self, record):
        if record['level'] == '0':  # top level category; has no name
            return {'name': self.backend_record.name}
        if record['name']:  # may be empty in storeviews
            return {'name': record['name']}

    @mapping
    def magento_id(self, record):
        return {'magento_id': record['category_id']}

    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}

    @mapping
    def parent_id(self, record):
        if not record.get('parent_id'):
            return
        binder = self.get_binder_for_model()
        category_id = binder.to_openerp(record['parent_id'], unwrap=True)
        mag_cat_id = binder.to_openerp(record['parent_id'])

        if category_id is None:
            raise MappingError("The product category with "
                               "magento id %s is not imported." %
                               record['parent_id'])
        return {'parent_id': category_id, 'magento_parent_id': mag_cat_id}
