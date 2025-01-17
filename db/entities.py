from pony.orm import *
from decimal import Decimal
from db.config import connect_db

db = connect_db()

class Address(db.Entity):
    _table_ = "addresses"
    address_id = PrimaryKey(int, auto=True)

    chainid = Required(int)
    address = Required(str)
    composite_key(chainid, address)

    is_contract = Required(bool)
    nickname = Optional(str)

    token = Optional('Token')


class Token(db.Entity):
    _table_ = "tokens"
    token_id = PrimaryKey(int, auto=True)

    symbol = Required(str)
    name = Required(str)
    decimals = Required(int)

    user_tx = Set('UserTx', reverse="vault")
    address = Required(Address, column="address_id")
    

class UserTx(db.Entity):
    _table_ = "user_txs"
    user_tx_id = PrimaryKey(int, auto=True)

    timestamp = Required(int)
    block = Required(int)
    hash = Required(str)
    log_index = Required(int)
    composite_key(hash, log_index)
    vault = Required(Token, reverse="user_tx", column="token_id")
    type = Required(str)
    from_address = Required(str, column="from")
    to_address = Required(str, column="to")
    amount = Required(Decimal,38,18)
    price = Required(Decimal,38,18)
    value_usd = Required(Decimal,38,18)
    gas_used = Required(Decimal,38,1)
    gas_price = Required(Decimal,38,1)
    

db.generate_mapping(create_tables=False)