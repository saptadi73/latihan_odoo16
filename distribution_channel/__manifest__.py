{
    'name': 'Distribution Channel',
    'version': '16.0.1.1.12',
    'category': 'Inventory',
    'summary': 'Multi-company distribution channel management',
    'description': """
Distribution Channel Management
================================
* Link retailer companies with distribution centers
* Auto-create inter-company sales orders from purchase orders
* Monitor order flow between companies
    """,
    'author': 'Saptadi Nurfarid, PT. Gagak Rimang Teknologi',
    'website': 'https://rimang.id',
    'depends': ['base', 'stock', 'purchase', 'sale', 'mail', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/res_company_views.xml',
        'views/stock_orderpoint_views.xml',
        'views/dc_monitor_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'views/product_views.xml',
        'views/product_template_views.xml',
        'wizard/replenish_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'distribution_channel/static/src/js/distribution_channel.js',
        ],
        'web.assets_qweb': [
            'distribution_channel/static/src/xml/distribution_channel_templates.xml',
        ],
        'point_of_sale.assets': [
            'distribution_channel/static/src/js/pos_product_stock.js',
            'distribution_channel/static/src/xml/pos_product_stock.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}