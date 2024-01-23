from setuptools import find_packages
from setuptools import setup

version = '0.9.1'

setup(
    name='certbot-nginx-unit',
    version=version,
    description="Nginx Unit plugin for Certbot",
    url='https://github.com/kea/certbot-nginx-unit',
    author="Manuel Baldassarri",
    author_email='m.baldassarri@gmail.com',
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: System Administrators",
        "Topic :: Security :: Cryptography",
        "Development Status :: 4 - Beta",
        "Environment :: Plugins",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(),
    install_requires=[
        'certbot',
    ],
    entry_points={
        'certbot.plugins': [
            'nginx_unit_installer = certbot_nginx_unit.installer:Installer',
        ],
    }
)
