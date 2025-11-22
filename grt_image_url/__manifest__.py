# -*- coding: utf-8 -*-
{
    'name': "grt_image_url",

    'summary': """
        - Res Partner Image URL

        """,

    'description': """
        Long description of module's purpose
    """,

    'author': "edi supriyanto",
    'website': "https://www.rimang.id",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    "data": [
        "views/res_partner_views.xml"
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
