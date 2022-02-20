from decimal import Decimal
from typing import Tuple

import numpy as np
import pandas as pd
from flask import Flask, jsonify
from flask_cors import CORS
from pandas._libs.tslibs.timedeltas import Timedelta

from inputs import address_inputs, method_input
from lots import (delete_active_lot, get_active_lot, prep_lots,
                  record_spent_lot, unspent_lots_for_export)
from sentry import setup_sentry
from transactions import transactions, tx_list_for_export, unique_tokens_sold

setup_sentry()

app = Flask(__name__)
CORS(app)


@app.route("/", methods=['POST'])
def yrs():
    GOOD_ADDRESSES, BAD_ADDRESSES = address_inputs()
    _in, _out = transactions(GOOD_ADDRESSES)
    
    if len(_in) == 0 and len(_out) == 0: return 'No transactions found for this address'

    taxable_events, leftover_unspent_lots = [], pd.DataFrame()
    
    for vault in unique_tokens_sold(_out):
      spent_lots, unspent_lots = prep_lots(_in, _out, vault, GOOD_ADDRESSES)
      assert type(unspent_lots) == pd.DataFrame, f'{type(unspent_lots)} {unspent_lots}' 
      
      # process vault
      for row in spent_lots.itertuples():
        taxable_events, unspent_lots = process_sale(row, taxable_events, unspent_lots)
        assert type(unspent_lots) == pd.DataFrame, f'{type(unspent_lots)} {unspent_lots}'
      
      # record all lots still unsold    
      leftover_unspent_lots = pd.concat([leftover_unspent_lots, unspent_lots]).reset_index(drop=True)
        
    # can't jsonify int64
    for i, event in enumerate(taxable_events):
      for k, v in event.items():
        if type(v) == np.int64:
          taxable_events[i][k] = int(v)

    # voila
    response = jsonify({
      'taxable events': taxable_events,
      'failures': BAD_ADDRESSES,
      'unspent lots': unspent_lots_for_export(leftover_unspent_lots),
      'transactions': tx_list_for_export(_in, _out),
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def process_sale(row, taxable_events, unspent_lots: pd.DataFrame):
    assert type(unspent_lots) == pd.DataFrame is pd.DataFrame, f'{type(unspent_lots)} {unspent_lots}'
    
    # cache these so we can manipulate them later
    sold_amount = row.amount
    sold_value_usd = row.value_usd
    sold_gas_used = row.gas_used
    
    i = 0
    #start
    while True:
      assert len(unspent_lots), f"No unspent lots remain. vault: {row.vault} iter: {i} hash: {row.hash} amount: {sold_amount}"
      active_lot, unspent_lots = get_active_lot(row, unspent_lots)
      assert type(unspent_lots) == pd.DataFrame is pd.DataFrame, f'{type(unspent_lots)} {unspent_lots}' 
      assert active_lot.timestamp <= row.timestamp

      if sold_amount > active_lot.amount:
        taxable_events.append(process_portion_of_sale(sold_amount, row, active_lot))
        
        # this taxable event is not fully resolved but you used the whole active lot
        unspent_lots = delete_active_lot(unspent_lots)
        assert type(unspent_lots) == pd.DataFrame is pd.DataFrame, f'{type(unspent_lots)} {unspent_lots}' 
        
        # you still have some tokens left to calc cost basis for
        sold_amount -= active_lot.amount
        sold_value_usd -= row.price * active_lot.amount
        sold_gas_used -= active_lot.gas_used

        # run loop again
        i += 1
        
      else:
        taxable_events.append(process_entire_sale(sold_amount, row, active_lot, sold_value_usd, sold_gas_used))
        unspent_lots = record_spent_lot(unspent_lots, active_lot, sold_amount, sold_gas_used)
        assert type(unspent_lots) == pd.DataFrame, f'{type(unspent_lots)} {unspent_lots}' 
        # on to the next one
        return taxable_events, unspent_lots


def process_portion_of_sale(sold_amount, row, active_lot):
    duration, period = get_duration(row, active_lot)
    portion_of_sale_processed = active_lot.amount / sold_amount
    return {
        'Chainid': row.chainid,
        'Vault': row.vault,
        'Symbol': row.symbol,
        'Entry Block': active_lot.block,
        'Entry Timestamp': active_lot.timestamp,
        'Entry Hash': active_lot.hash,
        'Entry Price': f'${round(active_lot.price,6)}',
        'Exit Block': row.block,
        'Exit Timestamp': row.timestamp,
        'Exit Hash': row.hash,
        'Exit Price': f'${round(row.price,6)}',
        'Duration': str(duration),
        'Amount': active_lot.amount,
        'Cost Basis': f'${round(active_lot.value_usd,2)}',
        'Proceeds': f'${round(row.price * active_lot.amount,2)}',
        'P/l': f'${round(row.price * active_lot.amount - active_lot.value_usd,2)}',
        'Period': period,
        'Gas to Enter': round(active_lot.gas_price * active_lot.gas_used / Decimal(1e18), 6),
        'Gas to Exit': round((row.gas_price * row.gas_used / Decimal(1e18)) * portion_of_sale_processed, 6),
        }


def process_entire_sale(sold_amount, row, active_lot, sold_value_usd, sold_gas_used): 
    duration, period = get_duration(row, active_lot)   
    portion_of_active_lot_used = sold_amount / active_lot.amount
    return {
        'Chainid': row.chainid,
        'Vault': row.vault,
        'Symbol': row.symbol,
        'Entry Block': active_lot.block,
        'Entry Timestamp': active_lot.timestamp,
        'Entry Hash': active_lot.hash,
        'Entry Price': f'${round(active_lot.price,6)}',
        'Exit Block': row.block,
        'Exit Timestamp': row.timestamp,
        'Exit Hash': row.hash,
        'Exit Price': f'${round(row.price,6)}',
        'Duration': str(duration),
        'Amount': round(sold_amount,8),
        'Cost Basis': f'${round(sold_amount * active_lot.price,2)}',
        'Proceeds':f'${round(sold_value_usd,2)}',
        'P/L':f'${round(sold_value_usd - (sold_amount * active_lot.price),2)}',
        'Period': period,
        'Gas to Enter': round((active_lot.gas_price * active_lot.gas_used / Decimal(1e18)) * portion_of_active_lot_used, 6),
        'Gas to Exit': round(row.gas_price * sold_gas_used / Decimal(1e18),6),
        }


def get_duration(row, active_lot) -> Tuple[Timedelta, str]:
    duration = row.timestamp - active_lot.timestamp
    period = 'long' if duration > Timedelta(days=365) else 'short'
    return duration,period
