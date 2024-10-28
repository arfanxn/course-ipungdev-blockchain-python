import sys 
import hashlib
import json

from time import time
from uuid import uuid4
from flask import Flask
from flask.globals import request
from flask.json import jsonify

import requests
from urllib.parse import urlparse   

class Blockchain:

    def __init__(self) -> None:
        self.difficulty_target = '0000' # 4 leading zeros
        self.nodes = set()
        self.chain = []
        self.current_transactions = []
        
        genesis_hash = self.hash_block(self.create_genesis_block())

        self.append_block(
            hash_of_previous_block=genesis_hash,
            nonce= self.proof_of_work(0, genesis_hash, []),
        )

    def add_node (self, address):
        parse_url = urlparse(address)
        self.nodes.add(parse_url.netloc)
        print(parse_url.netloc)

    def valid_chain(self, chain) -> bool:
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            if block['previous_hash'] != self.hash_block(last_block):
                return False
            if not self.valid_proof(
                current_index,
                block['hash_of_previous_block'], 
                block['transactions'],
                last_block['nonce'],
                ):
                return False
            last_block = block
            current_index += 1
        return True
    
    def update_blockchain(self):
        neighbours = self.nodes
        new_chain  = None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/blockchain')
            if response.status_code == 200:
                responseJson = response.json()
                responseJsonData = responseJson['data']
                length = responseJsonData['length']
                chain = responseJsonData['chain']
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain
        if new_chain:
            self.chain = new_chain
            return True
        return False

    def create_genesis_block(self) -> dict:
        return {
            'index': 0,
            'timestamp': time(),
            'transactions': [],
            'hash_of_previous_block': '0',
            'nonce': 0
        }

    def hash_block(self, block) -> str: 
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, index, hash_of_previous_block, transactions) -> int:
        nonce = 0;
        while self.valid_proof(index, hash_of_previous_block, transactions, nonce) is False: 
            nonce += 1
        return nonce
    
    def valid_proof(self, index, hash_of_previous_block, transactions, nonce) -> bool:
        guess = f'{index}{hash_of_previous_block}{transactions}{nonce}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == self.difficulty_target

    def append_block (self, nonce, hash_of_previous_block) -> None:
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'hash_of_previous_block': hash_of_previous_block,
            'nonce': nonce
        }
        self.current_transactions = []
        self.chain.append(block)    
        return block
    
    def add_transaction (self, sender, recipient, amount) -> None:
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })    
        return self.last_block['index'] + 1 
    
    @property 
    def last_block(self) -> dict:
        return self.chain[-1]
    

app = Flask(__name__) 

node_identifier = str(uuid4()).replace('-', '')

blockchain = Blockchain()

# routes 
@app.route('/blockchain', methods=['GET'])  
def full_chain():
    response = {
        'message' : 'Success',
        'data' : {
            'chain': blockchain.chain,
            'length': len(blockchain.chain),
        }
    }
    return jsonify(response), 200

@app.route('/mine', methods=['GET'])
def mine():
    blockchain.add_transaction(
        sender = '0',
        recipient = node_identifier,
        amount = 1
    )

    last_block_hash = blockchain.hash_block(blockchain.last_block)

    nonce = blockchain.proof_of_work(
        index = len(blockchain.chain),
        hash_of_previous_block = last_block_hash,
        transactions = blockchain.current_transactions
    )

    blockchain.append_block(
        nonce = nonce,
        hash_of_previous_block = last_block_hash,
    )

    response = {
        'message': 'New Block Forged',
        'data' : {
            'block': blockchain.last_block
        }
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction(): 
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return ('Unprocessable Entity', 422)
    
    index = blockchain.add_transaction(
        sender = values['sender'],
        recipient = values['recipient'],
        amount = values['amount']
    )
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.add_node(node)
    response = {
        'message': 'New nodes have been added',
        'data' : {
            'nodes': list(blockchain.nodes),
        }
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    updated = blockchain.update_blockchain()
    if updated:
        response = {
            'message': 'Our chain was updated',
            'data' : {
                'chain': blockchain.chain
            }
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'data' : {
                'chain': blockchain.chain
            }
        }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

