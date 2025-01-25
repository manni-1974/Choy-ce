import time
import hashlib
import os

class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.amount}"

class Block:
    def __init__(self, transactions, previous_hash, poh, timestamp=None):
        self.timestamp = timestamp if timestamp else time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.poh = poh
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        transaction_data = "".join(str(tx) for tx in self.transactions)
        block_data = f"{self.timestamp}{transaction_data}{self.previous_hash}{self.poh}"
        return hashlib.sha256(block_data.encode()).hexdigest()

class ProofOfHistory:
    def __init__(self):
        self.sequence = []

    def generate_hash(self, data):
        timestamp = time.time()
        prev_hash = self.sequence[-1] if self.sequence else "0"
        new_hash = hashlib.sha256(f"{data}{timestamp}{prev_hash}".encode()).hexdigest()
        self.sequence.append(new_hash)
        return new_hash

class Blockchain:
    def __init__(self):
        self.poh = ProofOfHistory()
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        poh_hash = self.poh.generate_hash("Genesis Block")
        genesis_transactions = [Transaction("System", "Genesis", 0)]
        return Block(genesis_transactions, "0", poh_hash)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, transactions):
        previous_block = self.get_latest_block()
        poh_hash = self.poh.generate_hash("Transactions Block")
        new_block = Block(transactions, previous_block.hash, poh_hash)
        self.chain.append(new_block)

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            if current_block.hash != current_block.calculate_hash():
                return False

            if current_block.previous_hash != previous_block.hash:
                return False

        return True

    def calculate_balances(self):
        balances = {}
        for block in self.chain:
            for tx in block.transactions:
                if tx.sender != "System":
                    balances[tx.sender] = balances.get(tx.sender, 0) - tx.amount
                balances[tx.receiver] = balances.get(tx.receiver, 0) + tx.amount
        return balances

from flask import Flask, jsonify, request

app = Flask(__name__)

my_blockchain = Blockchain()

@app.route('/')
def home():
    return "Welcome to the Blockchain App!"

@app.route('/blockchain', methods=['GET'])
def get_blockchain():
    chain_data = []
    for block in my_blockchain.chain:
        chain_data.append({
            "index": my_blockchain.chain.index(block),
            "timestamp": block.timestamp,
            "transactions": [{"sender": tx.sender, "receiver": tx.receiver, "amount": tx.amount} for tx in block.transactions],
            "previous_hash": block.previous_hash,
            "hash": block.hash,
            "poh": block.poh
        })
    return jsonify({"length": len(my_blockchain.chain), "chain": chain_data})

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    data = request.json
    sender = data.get("sender")
    receiver = data.get("receiver")
    amount = data.get("amount")
    if not sender or not receiver or not amount:
        return jsonify({"message": "Invalid transaction data"}), 400

    transaction = Transaction(sender, receiver, amount)
    my_blockchain.add_block([transaction])
    return jsonify({"message": "Transaction added and block mined!"})

@app.route('/balances', methods=['GET'])
def get_balances():
    balances = my_blockchain.calculate_balances()
    return jsonify(balances)

if __name__ == "__main__":
     app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)))
