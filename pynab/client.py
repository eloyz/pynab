"""YNAB Client written in Python."""
from collections import defaultdict
import json
import logging
import os
import shutil
from uuid import UUID

import arrow
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
        self._cache_dict = defaultdict(dict)

    def is_uuid(self, string):
        """Check if string is UUID."""
        try:
            UUID(string)
            return True
        except ValueError:
            return False

    def cache(self, key1, key2, data):
        """Cache at both memory and file level."""
        if key2 is None:
            # Update multiple items
            self._cache_dict.get(key1, {}).update(data)
        else:
            # Update item
            self._cache_dict.get(key1, {})[key2] = data
            data_from_file = self.from_file(key1)
            data_from_file.update(data)
            data = data_from_file

        self.to_file(key1, data)
        return data

    def clear_cache(self):
        """Clear memory and file level cache."""
        self._cache_dict = defaultdict(dict)
        shutil.rmtree('{}/'.format(self.cache_directory))

    def to_file(self, name, data):
        """Write data to file."""
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

    def get_from_cache(self, cache_key):
        """Use hiearchy of caches to retreive data."""
        # log if hit in memory cache and return
        if cache_key in self._cache_dict:
            logger.info('read from memory: %s', cache_key)
            return self._cache_dict[cache_key]

        # get via file cache; save results in memory
        data = self.from_file(cache_key)
        if data is not None:
            self._cache_dict[cache_key] = data

        # log if hit in file cache
        if self._cache_dict[cache_key]:
            logger.info('read from file %s', cache_key)

        return self._cache_dict.get(cache_key)


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
        self.session.headers['Authorization'] = 'Bearer {}'.format(self.token)
        self.session.headers['Content-Type'] = 'application/json'

        self.use_cache = use_cache

        # Last response object
        # Used for debugging; dig into the http response
        self.last_response = None

    def pluralize(self, string):
        """Pluralize cache keys."""
        last_letter = string.lower()[:-1]

        if last_letter == 'y':
            string = '%s_groups'.format(string)

        return '%ss'.format(string)

    def get_key(self, url_path):
        """Get key.

        Duplicate fn, but time constrained.
        """
        almost_tail, tail = url_path.split('/')[-2:]

        if self.is_uuid(tail):
            cache_key = self.pluralize(almost_tail)
        else:
            cache_key = tail

        return cache_key

    def get_keys_and_data(self, url_path, data):
        """Get keys and data based on url_path."""
        almost_tail, tail = url_path.split('/')[-2:]

        if self.is_uuid(tail):
            cache_key = self.pluralize(almost_tail)
            cache_uuid = tail
            data = data['data'][almost_tail]
        else:
            cache_key = tail
            cache_uuid = None

            if tail == 'categories':
                tail = 'category_groups'

            data = {item['id']: item for item in data['data'][tail]}

        return cache_key, cache_uuid, data

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
            response = self.get_from_cache(self.get_key(url))

        # Found in cache; exit
        if response:
            return response

        # Get via API endpoint
        response = self.session.get('{base_url}{url}'.format(
            base_url=self.base_url,
            url=url))

        # update rate_limit
        if 'x-rate-limit' in response.headers:
            self.rate_limit = response.headers['x-rate-limit']
            logger.debug('after %s: rate limit: %s', url, self.rate_limit)

        # save in cache
        if response.status_code == 200:
            key1, key2, data = self.get_keys_and_data(url, response.json())
            self.cache(key1, key2, data)
        else:
            logger.warning('%s %s', response.status_code, url)

        self.last_response = response
        return response.json()

    def post(self, url, data_dict):
        """POST request to YNAB API endpoint."""
        # Get via API endpoint
        post_url = '{base_url}{url}'.format(base_url=self.base_url, url=url)
        response = self.session.post(url=post_url, data=json.dumps(data_dict))

        # update rate_limit
        if 'x-rate-limit' in response.headers:
            self.rate_limit = response.headers['X-Rate-Limit']
            logger.debug('after %s: rate limit: %s', url, self.rate_limit)

        if response.status_code != 200:
            logger.warning('%s %s %s', response.status_code, url, response.json())

        self.last_response = response
        return response.json()

    def get_accounts(self):
        """Return accounts."""
        return self.get(
            '/budgets/{budget_id}/accounts'.format(
                budget_id=self.get_budget_id()))

    def get_budgets(self):
        """Return budgets."""
        return self.get('/budgets')

    def get_budget_id(self, name=None):
        """Return budget-id or None.

        Default:
            * Set budget id
            * First budget id
        """
        budgets = list(self.get_budgets().values())
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
        # TODO: Switched to dict; unordered
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
                budget_id=self.get_budget_id()))

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
                budget_id=self.get_budget_id()))

    def get_payee(self, payee_id):
        """Get payee."""
        url = '/budgets/{budget_id}/payees/{payee_id}'.format(
            budget_id=self.get_budget_id(),
            payee_id=payee_id)

        response = self.get(url)

        return response

    def get_payee_id(self, name, group_name=None):
        """Return payee-id or None.

        If no group_name is given,
        then return first payee that matches
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

        return self.get(url)

    def post_transaction(
        self,
        memo,
        date,
        amount,
        payee_id=None,
        payee_name=None,
        account_id=None,
        category_id=None,
        approved=True,
        cleared=True
    ):
        """Post transaction."""
        if not payee_id and not payee_name:
            raise UserWarning("payee_id or payee_name is required")

        amount = int(amount * 1000)
        # payee_name = self.get_payee(payee_id)['name']

        # Use 1st account if account_id is `None`
        account_id = self.get_accounts()[0]['id'] if account_id is None else account_id

        txn_dict = {
            "account_id": account_id,
            "date": arrow.get(date).isoformat(),
            "amount": amount,
            "payee_id": None,
            "payee_name": None,
            "category_id": category_id,
            "memo": memo,
            "cleared": "cleared" if cleared else "uncleared",
            "approved": approved,
            "flag_color": None,
            "import_id": None,
        }

        if payee_id:
            txn_dict['payee_id'] = payee_id
        else:
            txn_dict['payee_name'] = payee_name

        url = '/budgets/{budget_id}/transactions'.format(budget_id=self.get_budget_id())
        return self.post(url, {'transaction': txn_dict})['data']['transaction']
