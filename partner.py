# -*- encoding: utf-8 -*-
#########################################################################
#This module intergrates Open ERP with the magento core                 #
#Core settings are stored here                                          #
#########################################################################
#                                                                       #
# Copyright (C) 2009  Sharoon Thomas, Raphaël Valyi                     #
#                                                                       #
#This program is free software: you can redistribute it and/or modify   #
#it under the terms of the GNU General Public License as published by   #
#the Free Software Foundation, either version 3 of the License, or      #
#(at your option) any later version.                                    #
#                                                                       #
#This program is distributed in the hope that it will be useful,        #
#but WITHOUT ANY WARRANTY; without even the implied warranty of         #
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
#GNU General Public License for more details.                           #
#                                                                       #
#You should have received a copy of the GNU General Public License      #
#along with this program.  If not, see <http://www.gnu.org/licenses/>.  #
#########################################################################

from osv import osv, fields
import magerp_osv

class res_partner_category(magerp_osv.magerp_osv):
    _inherit = "res.partner.category"
    
    _columns = {
                    'tax_class_id':fields.integer('Tax Class ID'),
                }
res_partner_category()

class res_partner_address(magerp_osv.magerp_osv):
    _inherit = "res.partner.address"
    
    _columns = {
                    'lastname':fields.char('Last Name', size=100),
                    'is_magento_order_address':fields.boolean('Magento Order Address?'),
                }
    _defaults = {
                    'is_magento_order_address': lambda * a:False,
                 }
res_partner_address()

class res_partner(magerp_osv.magerp_osv):
    _inherit = "res.partner"
    
    _columns = {
                    'group_id':fields.many2one('res.partner.category', 'Magento Group(Category)'),
                    'store_id':fields.many2one('magerp.storeviews', 'Last Store View', help="Last store view where the customer has bought."),
                    'store_ids':fields.many2many('magerp.storeviews', 'magerp_storeid_rel', 'partner_id', 'store_id', 'Store Views'),
                    'website_id':fields.many2one('external.shop.group', 'Website'),
                    'created_in':fields.char('Created in', size=100),
                    'created_at':fields.datetime('Created Date'),
                    'updated_at':fields.datetime('Updated At'),
                    'emailid':fields.char('Email ID', size=100, help="Magento uses this email ID to correspond to the customer."),
                    'mag_vat':fields.char('Magento VAT', size=50, help="To be able to receive customer VAT number you must set it in Magento Admin Panel, menu System / Configuration / Client Configuration / Name and Address Options."),
                    'mag_birthday':fields.date('Birthday', help="To be able to receive customer birthday you must set it in Magento Admin Panel, menu System / Configuration / Client Configuration / Name and Address Options."),
                }

res_partner()
