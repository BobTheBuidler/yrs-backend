from typing import List, Tuple, Union
from brownie import convert
from brownie.convert.datatypes import EthAddress
from flask import request


def method_input() -> str:
    choices = ['FIFO','LIFO']
    assert request.json['type'] in choices, f'Input must be in ["FIFO","LIFO"]. Your request: {request.json}'
    return request.json['type']


def address_inputs() -> Tuple[List[EthAddress], List[EthAddress]]:
    good_addresses = [clean_address(address) for address in request.json['addresses'] if clean_address(address) is not None]
    bad_addresses = [address for address in request.json['addresses'] if clean_address(address) is None]
    return good_addresses, bad_addresses


def clean_address(address: str) -> Union[EthAddress,None]:
    try: return convert.to_address(address)
    except: pass
