"""Command line methods."""
import logging

import click

from pynab import Client

FORMAT = '%(name)s %(lineno)d: %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
def main():
    """Starting point."""
    pass


@main.command()
@click.argument('token', envvar='PYNAB_TOKEN')
@click.option('--budget-name', help="Defaults to first budget")
def get_budget_id(token, budget_name):
    """Print budget id."""
    client = Client(token)
    print(client.get_budget_id(name=budget_name))
