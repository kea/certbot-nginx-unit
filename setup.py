import os

from setuptools import find_packages
from setuptools import setup

test_extras = [
    "pytest",
]

install_requires = []
if not os.environ.get("SNAP_BUILD"):
    install_requires.extend(["acme>=1.21", "certbot>=1.21"])
else:
    install_requires.append("packaging")

setup(
    packages=find_packages(),
    install_requires=install_requires,
    extras_require={
        "test": test_extras,
    },
)
