from flask import Flask, jsonify, request
import time
import hashlib
import json
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
        self.poh = PoH()
        self.burned_tokens = {}
        self.frozen_tokens = {}
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
        token = transaction["token"]
        if self.frozen_tokens.get(token, False):
            return False

        tax = transaction['amount'] * IFChain.transaction_tax_rate
        net_amount = transaction['amount'] - tax
        if net_amount < 0:
            return False

        transaction['tax'] = tax
        transaction['net_amount'] = net_amount
        self.unconfirmed_transactions.append(transaction)
        return True

    def burn_tokens(self, token, amount):
        if token not in self.burned_tokens:
            self.burned_tokens[token] = 0
        self.burned_tokens[token] += amount

        burn_transaction = {
            "type": "burn",
            "token": token,
            "amount": amount
        }
        self.unconfirmed_transactions.append(burn_transaction)
        return True

    def freeze_token(self, token):
        self.frozen_tokens[token] = True
        return True

    def unfreeze_token(self, token):
        if token in self.frozen_tokens and self.frozen_tokens[token]:
            self.frozen_tokens[token] = False
            return True
        return False

    def mine(self):
        if not self.unconfirmed_transactions:
            return False

        last_block = self.last_block()
        poh_hash = self.poh.current_hash
        new_block = Block(index=last_block.index + 1,
                          timestamp=time.time(),
                          transactions=self.unconfirmed_transactions,
                          previous_hash=last_block.hash,
                          poh_hash=poh_hash)
        proof = self.proof_of_work(new_block)
        self.add_block(new_block, proof)
        self.unconfirmed_transactions = []
        return new_block.index

    def proof_of_work(self, block):
        block.nonce = 0
        computed_hash = block.compute_hash()
        while not computed_hash.startswith('0' * IFChain.difficulty):
            block.nonce += 1
            computed_hash = block.compute_hash()
        return computed_hash

ifchain = IFChain()

def poh_generator():
    while True:
        ifchain.poh.generate_hash()
        time.sleep(1)

poh_thread = threading.Thread(target=poh_generator, daemon=True)
poh_thread.start()

@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = [block.__dict__ for block in ifchain.chain]
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
        return "Transaction invalid", 400

@app.route('/burn_token', methods=['POST'])
def burn_token():
    data = request.get_json()
    if "token" not in data or "amount" not in data:
        return jsonify({"error": "Invalid burn request"}), 400
    if data["amount"] <= 0:
        return jsonify({"error": "Invalid burn amount"}), 400
    ifchain.burn_tokens(data["token"], data["amount"])
    return jsonify({"message": f"{data['amount']} {data['token']} burned."}), 200

@app.route('/freeze_token', methods=['POST'])
def freeze_token():
    data = request.get_json()
    if "token" not in data:
        return jsonify({"error": "Invalid freeze request"}), 400
    ifchain.freeze_token(data["token"])
    return jsonify({"message": f"Token {data['token']} frozen."}), 200

@app.route('/unfreeze_token', methods=['POST'])
def unfreeze_token():
    data = request.get_json()
    if "token" not in data:
        return jsonify({"error": "Invalid unfreeze request"}), 400
    if ifchain.unfreeze_token(data["token"]):
        return jsonify({"message": f"Token {data['token']} unfrozen."}), 200
    else:
        return jsonify({"error": "Token is not frozen or does not exist."}), 400

@app.route('/frozen_tokens', methods=['GET'])
def get_frozen_tokens():
    return jsonify({"frozen_tokens": ifchain.frozen_tokens})

@app.route('/mine', methods=['GET'])
def mine():
    result = ifchain.mine()
    if not result:
        return "No transactions to mine", 400
    return f"Block {result} is mined.", 200

@app.route('/poh', methods=['GET'])
def get_poh_history():
    return jsonify(ifchain.poh.get_history())

@app.route('/unconfirmed_transactions', methods=['GET'])
def get_unconfirmed_transactions():
    return jsonify({"unconfirmed_transactions": ifchain.unconfirmed_transactions})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
