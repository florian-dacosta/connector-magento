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

from openerp.addons.connector.queue.job import job
from openerp.addons.connector.unit.mapper import (mapping,
                                                  changed_by,
                                                  ExportMapper)
from openerp.addons.connector.exception import InvalidDataError
from openerp.addons.magentoerpconnect.unit.delete_synchronizer import (
        MagentoDeleteSynchronizer)
from openerp.addons.magentoerpconnect.unit.export_synchronizer import (
        MagentoExporter)
from openerp.addons.magentoerpconnect.partner import (
        AddressAdapter)
from openerp.addons.magentoerpconnect.backend import magento


@magento
class PartnerDeleteSynchronizer(MagentoDeleteSynchronizer):
    """ Partner deleter for Magento """
    _model_name = ['magento.res.partner',
                   'magento.address']


@magento
class PartnerExport(MagentoExporter):
    _model_name = ['magento.res.partner']

    def _after_export(self):
        address_ids = []
        data = {
            'magento_partner_id': self.binding_id,
        }
        if not self.binding_record.magento_address_bind_ids:
            data['openerp_id'] = self.binding_record.openerp_id.id
            data['is_default_billing'] = True
            data['is_default_shipping'] = True
            address_ids.append(self.session.create('magento.address', data))
        for child in self.binding_record.child_ids:
            if not child.magento_address_bind_ids:
                data['is_default_billing'] = False
                data['is_default_shipping'] = False
                data['openerp_id'] = child.id
                address_ids.append(self.session.create('magento.address', data))
        return True


    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        if not data.get('email', False):
            raise InvalidDataError("The partner does not have email "
                                   "but it is mandatory for magento")
        return


@magento
class AddressExport(MagentoExporter):
    _model_name = ['magento.address']


    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        for required_key in ('city', 'street', 'postcode', 'country_id', 'telephone'):
            if not data.get(required_key, False):
                raise InvalidDataError("The address does not contain %s "
                                       "but it is mandatory for magento" %
                                       required_key)
        return


@magento
class PartnerExportMapper(ExportMapper):
    _model_name = 'magento.res.partner'

    direct = [
            ('email', 'email'),
            ('birthday', 'dob'),
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('taxvat', 'taxvat'),
            ('group_id', 'group_id'),
            ('website_id', 'website_id'),
        ]

    @changed_by('name')
    @mapping
    def names(self, record):
        # FIXME base_surname needed
        if ' ' in record.name:
            parts = record.name.split()
            firstname = parts[0]
            lastname = ' '.join(parts[1:])
        else:
            lastname = record.name
            firstname = '-'
        return {'firstname': firstname, 'lastname': lastname}


@magento
class PartnerAddressExportMapper(ExportMapper):
    _model_name = 'magento.address'
 
    direct = [('zip', 'postcode'),
              ('city', 'city'),
              ('is_default_billing', 'is_default_billing'),
              ('is_default_shipping', 'is_default_shipping'),
              ]
 
 
    @mapping
    def partner(self, record):
        return {'partner_id': int(record.magento_partner_id.magento_id)}
 

    @mapping
    def names(self, record):
        # FIXME base_surname needed
        if ' ' in record.name:
            parts = record.name.split()
            firstname = parts[0]
            lastname = ' '.join(parts[1:])
        else:
            lastname = record.name
            firstname = '-'
        return {'firstname': firstname, 'lastname': lastname}
 

    @mapping
    def phone(self, record):
        return {'telephone': record.phone or record.mobile}

 
    @mapping
    def country(self, record):
        if record.country_id:
            return {'country_id': record.country_id.code}
 
 
    @mapping
    def region(self, record):
        if record.state_id:
            return {'region': record.state_id.name}
 
 
    @mapping
    def street(self, record):
        if record.street:
            street = [record.street]
            return {'street': street}

