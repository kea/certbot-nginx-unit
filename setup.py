from setuptools import find_packages
from setuptools import setup

test_extras = [
    "pytest",
]

install_requires = []

install_requires.extend([
    'certbot>=1.21',
])

setup(
    packages=find_packages(),
    install_requires=install_requires,
    extras_require={
        "test": test_extras,
    },
)
