from setuptools import find_packages
from setuptools import setup

version = "0.9.2"

test_extras = [
    "pytest",
]

setup(
    name="certbot-nginx-unit",
    version=version,
    description="Nginx Unit plugin for Certbot",
    url="https://github.com/kea/certbot-nginx-unit",
    author="Manuel Baldassarri",
    author_email="m.baldassarri@gmail.com",
    license="LICENSE",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: System Administrators",
        "Topic :: Security :: Cryptography",
        "Development Status :: 4 - Beta",
        "Environment :: Plugins",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(),
    install_requires=[
        "certbot",
    ],
    extras_require={
        "test": test_extras,
    },
    entry_points={
        "certbot.plugins": [
            "nginx_unit = certbot_nginx_unit.configurator:Configurator",
        ],
    },
)
