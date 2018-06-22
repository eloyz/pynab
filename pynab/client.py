"""YNAB Client written in Python."""
import json
import logging
import os
import shutil

import requests

FORMAT = '%(name)s %(lineno)d: %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = os.path.realpath(os.path.dirname(__file__))


class CacheMeOutside:
    """Object that comes with cache attributes.

    In memory and file level cache object.
    """

    def __init__(self):
        """Set cache directories and template."""
        self.cache_directory = os.path.join(ROOT, 'cache')
        self.cache_path_template = os.path.join(self.cache_directory, '{}.json')
        self._ynab_cache = {}

    def cache(self, name, data):
        """Cache at both memory and file level."""
        cache_key = name.strip().lower().replace('/', '_')
        self._ynab_cache[cache_key] = data
        self.to_file(cache_key, data)
        return data

    def clear_cache(self):
        """Clear memory and file level cache."""
        self._ynab_cache = {}
        shutil.rmtree('{}/'.format(self.cache_directory))

    def to_file(self, name, data):
        """Write data to file.

        If file not found; blow up.
        """
        with open(self.cache_path_template.format(name), 'w') as f:
            f.write(json.dumps(data))

    def from_file(self, name):
        """Read data from file.

        If file not found; it's ok; ignore.
        """
        try:
            with open(self.cache_path_template.format(name), 'r') as f:
                data = f.read()
        except FileNotFoundError:
            return

        return json.loads(data)

    def get_from_cache(self, name):
        """Use hiearchy of caches to retreive data."""
        cache_key = name.strip().lower().replace('/', '_')

        # log if hit in memory cache and return
        if cache_key in self._ynab_cache:
            logger.debug('read from memory: %s', name)
            return self._ynab_cache[cache_key]

        # get via file cache; save results in memory
        self._ynab_cache[cache_key] = self.from_file(cache_key)

        # log if hit in file cache
        if self._ynab_cache[cache_key]:
            logger.debug('read from file %s', name)

        return self._ynab_cache.get(cache_key)


class Client(CacheMeOutside):
    """Convenience object that interacts with YNAB API."""

    def __init__(self, token, use_cache=True):
        """Store token.

        :param token required:
        """
        super().__init__()

        self.base_url = 'https://api.youneedabudget.com/v1'
        self.token = token

        # Assume one static budget.
        self._budget_id = None

        # Limit is reset 1 hour after first request is received
        # 200 requests per hour, based on client ip address
        self.rate_limit = None

        # initialize session
        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Bearer {}'.format(self.token)})

        self.use_cache = use_cache

        # Last response object
        # Used for debugging; dig into the http response
        self.last_response = None

    def set_budget_id(self, budget_id):
        """Set budget_id."""
        self._budget_id = budget_id

    # TODO: use_cache=True
    def get(self, url, use_cache=True):
        """GET request to YNAB API endpoint.

        - cache 200 responses
        - read from cache first
        """
        if use_cache and self.use_cache:
            response = self.get_from_cache(url)

        # Found in cache; exit
        if response:
            return response

        # Get via API endpoint
        response = self.session.get('{base_url}{url}'.format(
            base_url=self.base_url,
            url=url))

        # update rate_limit
        self.rate_limit = response.headers['X-Rate-Limit']
        logger.debug('after %s: rate limit: %s', url, self.rate_limit)

        # save in cache
        if response.status_code == 200:
            self.cache(url, response.json())
        else:
            logger.warning('%s %s', response.status_code, url)

        self.last_response = response
        return response.json()

    def get_accounts(self):
        """Return accounts."""
        return self.get(
            '/budgets/{budget_id}/accounts'.format(
                budget_id=self.get_budget_id()))['data']['accounts']

    def get_budgets(self):
        """Return budgets."""
        return self.get('/budgets')['data']['budgets']

    def get_budget_id(self, name=None):
        """Return budget-id or None.

        Default:
            * Set budget id
            * First budget id
        """
        budgets = self.get_budgets()
        budget_id = None

        # try getting budget id via name
        if name is not None:
            for budget in budgets:
                if name.strip().lower() == budget['name'].strip().lower():
                    budget_id = budget['id']
            if budget_id is None:
                logger.debug('budget name %s, not found', name)

        # try getting budget id via what's already set
        if budget_id is None:
            budget_id = self._budget_id

        # try getting the first budget id in the list
        if budget_id is None:
            try:
                budget_id = budgets[0]['id']
            except IndexError:
                budget_id = None

        # set budget id if not set yet
        if self._budget_id is None:
            self.set_budget_id(budget_id)

        return budget_id

    def get_categories(self):
        """Return categories via category groups.

        That's the YNAB API response structure.
        """
        return self.get(
            '/budgets/{budget_id}/categories'.format(
                budget_id=self.get_budget_id()))['data']['category_groups']

    def get_category_id(self, name, group_name=None):
        """Return category-id or None.

        If no group_name is given,
        then return first category that matches
        """
        category_groups = self.get_categories()

        # expensive; but but small byte size
        for category_group in category_groups:

            if group_name is not None:
                group_name != category_group['name'].strip().lower()
                continue  # skip this group of categories

            for category in category_group['categories']:
                logger.info('%s %s', name.strip().lower(), category['name'].strip().lower())
                if name.strip().lower() == category['name'].strip().lower():
                    return category['id']

    def get_payees(self):
        """Return payees."""
        return self.get(
            '/budgets/{budget_id}/payees'.format(
                budget_id=self.get_budget_id()))['data']['payees']

    def get_payee_id(self, name, group_name=None):
        """Return category-id or None.

        If no group_name is given,
        then return first category that matches
        """
        payees = self.get_payees()

        # expensive; but but small byte size
        for payee in payees:
            if name.strip().lower() == payee['name'].strip().lower():
                return payee['id']

    def get_transactions(self, category_id=None, payee_id=None):
        """Get transactions.

        Limit the set by passing:
        - category_id
        - payee_id
        """
        url = '/budgets/{budget_id}/transactions'.format(
            budget_id=self.get_budget_id())

        if category_id is not None:
            url = '/budgets/{budget_id}/categories/{category_id}/transactions'.format(
                budget_id=self.get_budget_id(),
                category_id=category_id)
        elif payee_id is not None:
            url = '/budgets/{budget_id}/payees/{payee_id}/transactions'.format(
                budget_id=self.get_budget_id(),
                payee_id=payee_id)

        return self.get(url)['data']['transactions']

