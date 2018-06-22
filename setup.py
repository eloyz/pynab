"""Install pynab library."""
from distutils.core import setup
import os


def pip_requirements(extra=None):
    """Return list of requirements."""
    if not os.environ.get('SKIP_INSTALL_REQUIRES'):
        requirements_path = "requirements.pip"
        with open(requirements_path) as f:
            return f.readlines()
    return []


setup(
    name='pynab',
    version='0.0.1',
    description='YNAB client',
    author='Eloy Zuniga Jr.',
    author_email='eloyz.email@gmail.com',
    url='http://github.com/eloyz/pynab',
    py_modules=[
        'pynab',
        'pynab.cli'
    ],
    install_requires=pip_requirements(),
    entry_points={
        'console_scripts': [
            "pynab = pynab.cli.main:main"
        ]
    },
)
