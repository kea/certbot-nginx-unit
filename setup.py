from setuptools import setup

setup(
    name='certbot-nginx-unit',
    package='installer.py',
    install_requires=[
        'certbot',
    ],
    entry_points={
        'certbot.plugins': [
            'nginx_unit_installer = installer:Installer',
        ],
    },
)