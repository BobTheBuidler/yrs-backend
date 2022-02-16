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
from transactions import transactions, tx_list_for_export, unique_tokens_sold

app = Flask(__name__)
CORS(app)


@app.route("/", methods=['POST'])
def yrs():
    METHOD = method_input()
    GOOD_ADDRESSES, BAD_ADDRESSES = address_inputs()
    _in, _out = transactions(GOOD_ADDRESSES)
    
    taxable_events, leftover_unspent_lots = [], pd.DataFrame()
    
    for vault in unique_tokens_sold(_out):
      spent_lots, unspent_lots = prep_lots(_in, _out, vault, GOOD_ADDRESSES, METHOD)
      
      # process vault
      for row in spent_lots.itertuples(): taxable_events, unspent_lots = process_sale(row, METHOD, taxable_events, unspent_lots)
      
      # record all lots still unsold    
      leftover_unspent_lots = pd.concat([leftover_unspent_lots, unspent_lots]).reset_index(drop=True)
        
    # voila
    response = jsonify({
      'taxable events': taxable_events,
      'failures': BAD_ADDRESSES,
      'unspent lots': unspent_lots_for_export(leftover_unspent_lots),
      'transactions': tx_list_for_export(_in, _out),
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def process_sale(row, method, unspent_lots, taxable_events):
    # cache these so we can manipulate them later
    sold_amount = row.amount
    sold_value_usd = row.value_usd
    sold_gas_used = row.gas_used
    
    #start
    while True:
      active_lot, unspent_lots = get_active_lot(row, method, unspent_lots)
      assert active_lot.timestamp <= row.timestamp
      if sold_amount > active_lot.amount:
        taxable_events.append(process_portion_of_sale(sold_amount, row, active_lot))
        
        # this taxable event is not fully resolved but you used the whole active lot
        unspent_lots = delete_active_lot(unspent_lots)
        
        # you still have some tokens left to calc cost basis for
        sold_amount -= active_lot.amount
        sold_value_usd -= row.price * active_lot.amount
        sold_gas_used -= active_lot.gas_used

        # run loop again
        
      else:
        taxable_events.append(process_entire_sale(sold_amount, row, active_lot, sold_value_usd, sold_gas_used))
        record_spent_lot(unspent_lots, active_lot, sold_amount, sold_gas_used)
        # on to the next one
        return taxable_events, unspent_lots


def process_portion_of_sale(sold_amount, row, active_lot):
    duration, period = get_duration(row, active_lot)
    portion_of_sale_processed = active_lot.amount / sold_amount
    return {
        'chainid': row.chainid,
        'vault': row.vault,
        'symbol': row.symbol,
        'entry block': active_lot.block,
        'entry timestamp': active_lot.timestamp,
        'entry hash': active_lot.hash,
        'entry price': f'${round(active_lot.price,6)}',
        'exit block': row.block,
        'exit timestamp': row.timestamp,
        'exit hash': row.hash,
        'exit price': f'${round(row.price,6)}',
        'duration': str(duration),
        'amount': active_lot.amount,
        'cost basis': f'${round(active_lot.value_usd,2)}',
        'proceeds': f'${round(row.price * active_lot.amount,2)}',
        'p/l': f'${round(row.price * active_lot.amount - active_lot.value_usd,2)}',
        'period': period,
        'gas to enter': round(active_lot.gas_price * active_lot.gas_used / Decimal(1e18), 6),
        'gas to exit': round((row.gas_price * row.gas_used / Decimal(1e18)) * portion_of_sale_processed, 6),
        }


def process_entire_sale(sold_amount, row, active_lot, sold_value_usd, sold_gas_used): 
    duration, period = get_duration(row, active_lot)   
    portion_of_active_lot_used = sold_amount / active_lot.amount
    return {
        'chainid': row.chainid,
        'vault': row.vault,
        'symbol': row.symbol,
        'entry block': active_lot.block,
        'entry timestamp': active_lot.timestamp,
        'entry hash': active_lot.hash,
        'entry price': f'${round(active_lot.price,6)}',
        'exit block': row.block,
        'exit timestamp': row.timestamp,
        'exit hash': row.hash,
        'exit price': f'${round(row.price,6)}',
        'duration': str(duration),
        'amount': round(sold_amount,8),
        'cost basis': f'${round(sold_amount * active_lot.price,2)}',
        'proceeds':f'${round(sold_value_usd,2)}',
        'p/l':f'${round(sold_value_usd - (sold_amount * active_lot.price),2)}',
        'period': period,
        'gas to enter': round((active_lot.gas_price * active_lot.gas_used / Decimal(1e18)) * portion_of_active_lot_used, 6),
        'gas to exit': round(row.gas_price * sold_gas_used / Decimal(1e18),6),
        }


def get_duration(row, active_lot) -> Tuple[Timedelta, str]:
    duration = row.timestamp - active_lot.timestamp
    period = 'long' if duration > Timedelta(days=365) else 'short'
    return duration,period
