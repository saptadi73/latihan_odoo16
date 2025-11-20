{
    'name': 'Aplikasi Simpan Pinjam',
    'version': '1.0',
    'description': 'Aplikasi Simpan Pinjam untuk mengelola data nasabah, simpanan, pinjaman, pembayaran, dan pencairan pinjaman.',
    'summary': 'Aplikasi Simpan Pinjam yang lengkap untuk koperasi atau lembaga keuangan mikro.',
    'author': 'Saptadi Nurfarid',
    'website': 'https://rimang.id',
    'license': 'LGPL-3',
    'category': 'Koperasi',
    'depends': [
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/nasabah_views.xml',
        'views/simpanan_views.xml',
        'views/pinjaman_views.xml',
        'views/pencairan_pinjaman_views.xml',
        'views/pembayaran_pinjaman_views.xml',
        'views/menu.xml',
    ],
    'demo': [
        ''
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        
    }
}