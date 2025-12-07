{
    'name': 'Distribution Channel',
    'version': '16.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Multi-company distribution channel management',
    'description': """
Distribution Channel Management
================================
* Link retailer companies with distribution centers
* Auto-create inter-company sales orders from purchase orders
* Monitor order flow between companies
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'stock', 'purchase', 'sale', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/res_company_views.xml',
        'views/stock_orderpoint_views.xml',
        'views/dc_monitor_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'wizard/replenish_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}