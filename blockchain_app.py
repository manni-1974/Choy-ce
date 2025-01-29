from flask import Flask, jsonify, request
import time
import hashlib
import json
import schedule
import threading

app = Flask(__name__)

class PoH:
    def __init__(self):
        self.current_hash = self.generate_initial_hash()
        self.history = []

    def generate_initial_hash(self):
        return hashlib.sha256(str(time.time()).encode()).hexdigest()

    def generate_hash(self):
        new_hash = hashlib.sha256(self.current_hash.encode()).hexdigest()
        self.history.append({"timestamp": time.time(), "hash": new_hash})
        self.current_hash = new_hash

    def get_history(self):
        return self.history

class Block:
    def __init__(self, index, timestamp, transactions, previous_hash, poh_hash):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.poh_hash = poh_hash
        self.nonce = 0

    def compute_hash(self):
        block_string = json.dumps(self.__dict__, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

class IFChain:
    difficulty = 2
    transaction_tax_rate = 0.03

    def __init__(self):
        self.unconfirmed_transactions = []
        self.chain = []
        self.frozen_tokens = set()  # Stores frozen tokens
        self.poh = PoH()
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(0, time.time(), [], "0", self.poh.current_hash)
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    def last_block(self):
        return self.chain[-1]

    def add_block(self, block, proof):
        previous_hash = self.last_block().hash
        if previous_hash != block.previous_hash:
            return False
        if not self.is_valid_proof(block, proof):
            return False
        block.hash = proof
        self.chain.append(block)
        return True

    def is_valid_proof(self, block, block_hash):
        return (block_hash.startswith('0' * IFChain.difficulty) and
                block_hash == block.compute_hash())

    def add_new_transaction(self, transaction):
        if transaction['token'] in self.frozen_tokens:
            return False  # Reject transaction if token is frozen
        
        tax = transaction['amount'] * IFChain.transaction_tax_rate
        net_amount = transaction['amount'] - tax
        if net_amount < 0:
            return False
        transaction['tax'] = tax
        transaction['net_amount'] = net_amount
        self.unconfirmed_transactions.append(transaction)
        return True

    def freeze_token(self, token):
        self.frozen_tokens.add(token)

    def unfreeze_token(self, token):
        self.frozen_tokens.discard(token)

ifchain = IFChain()

def poh_generator():
    while True:
        ifchain.poh.generate_hash()
        time.sleep(1)

poh_thread = threading.Thread(target=poh_generator, daemon=True)
poh_thread.start()

@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = []
    for block in ifchain.chain:
        chain_data.append(block.__dict__)
    return jsonify({"length": len(chain_data), "chain": chain_data})

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    tx_data = request.get_json()
    required_fields = ["sender", "receiver", "amount", "token"]
    if not all(field in tx_data for field in required_fields):
        return "Invalid transaction data", 400
    if ifchain.add_new_transaction(tx_data):
        return "Transaction added to the pool", 201
    else:
        return "Transaction invalid or token is frozen", 400

@app.route('/mine', methods=['GET'])
def mine():
    result = ifchain.mine()
    if not result:
        return "No transactions to mine", 400
    return f"Block {result} is mined.", 200

@app.route('/poh', methods=['GET'])
def get_poh_history():
    return jsonify(ifchain.poh.get_history())

@app.route('/freeze_token', methods=['POST'])
def freeze_token():
    data = request.get_json()
    token = data.get("token")
    if not token:
        return "Token name required", 400
    ifchain.freeze_token(token)
    return f"Token {token} is now frozen.", 200

@app.route('/unfreeze_token', methods=['POST'])
def unfreeze_token():
    data = request.get_json()
    token = data.get("token")
    if not token:
        return "Token name required", 400
    ifchain.unfreeze_token(token)
    return f"Token {token} is now unfrozen.", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
