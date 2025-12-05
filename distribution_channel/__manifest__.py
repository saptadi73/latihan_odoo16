{
    'name': 'Distribution Channel',
    'version': '1.0.2',
    'description': 'Distribution Channel Management Module',
    'summary': 'Auto SO/PO Creation between Retailer & DC',
    'author': 'Saptadi Nurfarid, PT. Gagak Rimang Teknologi',
    'website': 'https://rimang.id',
    'license': 'LGPL-3',
    'category': 'Inventory',
    'depends': [
        'base',
        'sale_management',
        'purchase',
        'stock',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/retail_order_views.xml',
        'views/retail_order_report_views.xml',
    ],
    'demo': [
        ''
    ],
    'installable': True,
    'application': True,
    'assets': {
        
    }
}