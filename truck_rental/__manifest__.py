{
    'name': 'truck Rental',
    'version': '1.4',
    'description': 'Aplikasi Pendukung Fleet Managemnent System untuk rental truck',
    'summary': 'Untuk Sewa Truck',
    'author': 'Saptadi Nurfarid',
    'website': 'https://rimang.id',
    'license': 'LGPL-3',
    'category': 'automotive',
    'depends': [
        'base',
        'fleet',
        'sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rental_views.xml',
        'views/fleet_vehicle_views.xml',
    ],
    'demo': [
        ''
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        
    }
}