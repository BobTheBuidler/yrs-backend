
from decimal import Decimal
from typing import List, Tuple

import pandas as pd
from pony.orm import db_session, select

from db.entities import UserTx


@db_session
def transactions(GOOD_ADDRESSES: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    '''
    Returns a tuple of DataFrames `(inboundTxs,outboundTxs)`
    '''
    _in = select(
        (
            t.timestamp, 
            t.block, 
            t.hash, 
            t.vault.address.chainid, 
            t.vault.symbol,
            t.vault.address.address, 
            t.type, 
            t.from_address, 
            t.to_address, 
            t.amount, 
            t.price, 
            t.value_usd,
            t.gas_used,
            t.gas_price
        ) for t in UserTx 
            if t.to_address in GOOD_ADDRESSES
            # users can be weird and send things to themselves, we don't care about those
            and t.from_address != t.to_address 
            # if for some reason we have a tx with 0 amount, ignore
            # see `0x05ba797ba30fc4416e1932ac490a89613c525e0b5da4b95b79e9a4e28926e94e`
            and t.amount > 0
        )
    _out = select(
        (
            t.timestamp, 
            t.block, 
            t.hash, 
            t.vault.address.chainid, 
            t.vault.symbol,
            t.vault.address.address, 
            t.type, 
            t.from_address, 
            t.to_address, 
            t.amount, 
            t.price, 
            t.value_usd,
            t.gas_used,
            t.gas_price
        ) for t in UserTx
            if t.from_address in GOOD_ADDRESSES
            # users can be weird and send things to themselves, we don't care about those
            and t.from_address != t.to_address 
            # if for some reason we have a tx with 0 amount, ignore
            # see `0x05ba797ba30fc4416e1932ac490a89613c525e0b5da4b95b79e9a4e28926e94e`
            and t.amount > 0
        )
    
    # create DataFrames
    _in, _out = pd.DataFrame(_in), pd.DataFrame(_out)

    if len(_in):
        _in.columns = ['timestamp','block','hash','chainid','symbol','vault','type','from_address','to_address','amount','price','value_usd','gas_used','gas_price']
        _in.timestamp = pd.to_datetime(_in.timestamp,unit='s')
    if len(_out):
        _out.columns = ['timestamp','block','hash','chainid','symbol','vault','type','from_address','to_address','amount','price','value_usd','gas_used','gas_price']
        _out = _out.sort_values(['vault','timestamp'],ascending=[True,True]).reset_index(drop=True)
        _out.timestamp = pd.to_datetime(_out.timestamp,unit='s')

    return _in, _out

def unique_tokens_sold(tokens_out: pd.DataFrame) -> List[str]:
    try: return tokens_out['vault'].unique()
    except: return []
    
def tx_list_for_export(_in: pd.DataFrame, _out: pd.DataFrame) -> List[dict]:
    txs = pd.concat([_in,_out]).sort_values(by='block')
    txs['gas_cost'] = txs.gas_price * txs.gas_used / Decimal(1e18)
    txs = txs.drop(columns=['gas_price','gas_used'])
    try:
        return [{
            'Block': row.block,
            'Timestamp': row.timestamp,
            'Hash': row.hash,
            'Type': row.type,
            'Chainid': row.chainid,
            'From Address': row.from_address,
            'To Address': row.to_address,
            'Symbol': row.symbol,
            'Vault': row.vault,
            'Amount': row.amount,
            'Price': row.price,
            'Value USD': row.value_usd,
            'Gas Cost': row.gas_cost
        } for row in txs.itertuples()]
    except: raise Exception(txs.columns)
    