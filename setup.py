from setuptools import find_packages
from setuptools import setup

test_extras = [
    "pytest",
]

setup(
    packages=find_packages(),
    install_requires=[
        "certbot",
    ],
    extras_require={
        "test": test_extras,
    },
)
