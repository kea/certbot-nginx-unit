import os

from setuptools import find_packages
from setuptools import setup

test_extras = [
    "pytest",
]

certbot_version = '2.12.0.dev0'

install_requires = []
if not os.environ.get("SNAP_BUILD"):
    install_requires.extend([f'acme>={certbot_version}', f'certbot>={certbot_version}'])
else:
    install_requires.append("packaging")

setup(
    python_requires='>=3.8',
    packages=find_packages(),
    install_requires=install_requires,
    extras_require={
        "test": test_extras,
    },
)
