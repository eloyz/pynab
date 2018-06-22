
# YNAB Cilent
Python 3 Client for You Need a Budget  
https://www.youneedabudget.com/


#### Get all transactions
```python
from ynab import Client

client = Client('<token>')
transactions = client.get_transactions()
```

#### Get transactions, limit by category
```python
from ynab import Client

client = Client('<token>')
category_id = client.get_category_id('gas')
transactions = client.get_transactions(category_id=category_id)
```

#### Get transactions, limit by payee
```python
from ynab import Client

client = Client('<token>')
payee_id = client.get_payee_id('gas')
transactions = client.get_transactions(payee_id=payee_id)
```

#### Get budget id
```python
from ynab import Client

client = Client('<token>')

client.get_budget_id()  # first budget if name is not passed
client.get_budget_id('My Budget')
```

#### Get category id
```python
from ynab import Client

client = Client('<token>')

client.get_category_id('gas')  # first group if name is not unique
client.get_category_id('gas', group_name='house')
```

#### Get payee id
```python
from ynab import Client

client = Client('<token>')

client.get_payee_id('gas')  # first group if name is not unique
client.get_payee_id('gas', group_name='house')
```

#### Get accounts
```python
from ynab import Client

client = Client('<token>')
client.accounts()
```

#### Get budgets
```python
from ynab import Client

client = Client('<token>')
client.budgets()
```

#### Get categories
```python
from ynab import Client

client = Client('<token>')
client.categories()
```

#### Get payees
```python
from ynab import Client

client = Client('<token>')
client.payees()
```

#### Which budget is used
YNAB allows you to have multiple budgets. I'm making the **assumption** that most of your activity will remain in one budget. By default I use the first budget available if no budget name is specified. Once a budget has been selected explicitly or by default, that budget will continue to be used. You can check which budget is being used by calling `client._budget_id`.

You can also explictly set which budget should be used via `client.set_budget_id('<budget id>')`.

#### All methods return strings or dictionaries

> There are plenty of methods that aren't available yet and I hope the client is easy enough to understand that I can get some contributors to help out. Thanks everyone and I hope this client helps you.
> 
> I plan to write unit-tests as well :/
