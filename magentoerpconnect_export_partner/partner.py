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
        data = {
            'magento_partner_id': self.binding_id,
        }
        if not self.binding_record.magento_address_bind_ids:
            data['openerp_id'] = self.binding_record.openerp_id.id
            data['is_default_billing'] = True
            data['is_default_shipping'] = True
            self.session.create('magento.address', data)
        for child in self.binding_record.child_ids:
            if not child.magento_address_bind_ids:
                data['is_default_billing'] = False
                data['is_default_shipping'] = False
                data['openerp_id'] = child.id
                self.session.create('magento.address', data)

    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        if not data.get('email'):
            raise InvalidDataError("The partner does not have an email "
                                   "but it is mandatory for Magento")


@magento
class AddressExport(MagentoExporter):
    _model_name = ['magento.address']


    def _export_dependencies(self):
        """ Export the dependencies for the record"""
        relation = self.binding_record.parent_id or self.binding_record.openerp_id
        self._export_dependency(relation, 'magento.res.partner',
                                PartnerExport)

    def _validate_data(self, data):
        """ Check if the values to import are correct

        Pro-actively check before the ``Model.create`` or
        ``Model.update`` if some fields are missing

        Raise `InvalidDataError`
        """
        missing_fields = []
        for required_key in ('city', 'street', 'postcode', 'country_id', 'telephone'):
            if not data.get(required_key):
                missing_fields.append(required_key)
        if missing_fields:
            raise InvalidDataError("The address does not contain one or several "
                                   "mandatory fields for Magento : %s" %
                                   missing_fields)


@magento
class PartnerExportMapper(ExportMapper):
    _model_name = 'magento.res.partner'

    direct = [
            ('birthday', 'dob'),
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('taxvat', 'taxvat'),
            ('group_id', 'group_id'),
            ('website_id', 'website_id'),
            ('magento_password', 'password_hash'),
        ]

    @mapping
    def email(self, record):
        email = record.emailid or record.email
        return {'email': email}

    @changed_by('name')
    @mapping
    def names(self, record):
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
        binder = self.get_binder_for_model('magento.res.partner')
        erp_partner_id = record.parent_id and record.parent_id.id or record.openerp_id.id
        mag_partner_id = binder.to_backend(erp_partner_id, True)
        return {'partner_id': mag_partner_id}
 
    @mapping
    def names(self, record):
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
            street = record.street
        if record.street2:
            street = ['\n'.join([street, record.street2])]
        if street:
            return {'street': street}

