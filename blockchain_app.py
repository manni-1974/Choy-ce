from flask import Flask, jsonify, request
import time
import hashlib
import json
import os
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
        self.CONTRACT_STATE_FILE = "contract_states.json"
        self.unconfirmed_transactions = []
        self.chain = []
        self.poh = PoH()
        self.create_genesis_block()
        self.token_supply = 500_000_000
        self.frozen_tokens = {}
        self.burned_tokens = 0
        self.inflation_schedule = self.generate_inflation_schedule()
        self.applied_inflation_years = set()
        self.minted_tokens = {}
        self.contracts = {}
        self.load_contract_state()
        
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
        if transaction["token"] in self.frozen_tokens and self.frozen_tokens[transaction["token"]]:
            return False

        tax = transaction['amount'] * IFChain.transaction_tax_rate
        net_amount = transaction['amount'] - tax
        if net_amount < 0:
            return False
        transaction['tax'] = tax
        transaction['net_amount'] = net_amount
        self.unconfirmed_transactions.append(transaction)
        return True

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

    def freeze_token(self, token):
        self.frozen_tokens[token] = True
        return True

    def unfreeze_token(self, token):
        if token in self.frozen_tokens and self.frozen_tokens[token]:
            self.frozen_tokens[token] = False
            return True
        return False

    def burn_tokens(self, token, amount):
        if token not in self.frozen_tokens or self.frozen_tokens[token]:
            return False
        if amount > self.token_supply:
            return False
        self.token_supply -= amount
        self.burned_tokens += amount
        return True

    def mint_tokens(self, token, amount):
        if token in self.frozen_tokens and self.frozen_tokens[token]:
            return False
        if token not in self.minted_tokens:
            self.minted_tokens[token] = 0
        self.minted_tokens[token] += amount
        self.token_supply += amount
        return True
    
    def generate_inflation_schedule(self):
        return {
            2025: 0.0354,
            2026: 0.0301,
            2027: 0.0256,
            2028: 0.0218,
            2029: 0.0185,
            2030: 0.0157,
        }

    def apply_inflation(self):
        current_year = int(time.strftime("%Y"))
        if current_year in self.inflation_schedule and current_year not in self.applied_inflation_years:
            new_tokens = int(self.token_supply * self.inflation_schedule[current_year])
            self.mint_tokens("IFC", new_tokens)
            self.applied_inflation_years.add(current_year)
            print(f"Minted {new_tokens} IFC for inflation in {current_year}.")
            return True
        return False

    def get_total_supply(self):
        return self.token_supply
        
    def deploy_contract(self, contract_name, contract_code):
        """Deploy a new smart contract."""
        if contract_name in self.contracts:
            return False
        
        self.contracts[contract_name] = {"code": contract_code, "state": {}}
        self.save_contract_state()
        return True

    def execute_contract(self, contract_name, function_name, params):
        """Execute an existing smart contract function safely and persist state."""
        if contract_name not in self.contracts:
            return False

        contract_code = self.contracts[contract_name]["code"]
        contract_state = self.contracts[contract_name]["state"]

        local_scope = {"state": contract_state}
        exec(contract_code, local_scope)

        if function_name in local_scope and callable(local_scope[function_name]):
            result = local_scope[function_name](**params)
            self.contracts[contract_name]["state"] = local_scope["state"]
            self.save_contract_state()
            return result

        return False
    
    def save_contract_state(self):
        """Save all smart contract states to a file for persistence."""
        with open(self.CONTRACT_STATE_FILE, "w") as f:
            json.dump(self.contracts, f)

    def load_contract_state(self):
        """Load contract states from a file when the blockchain starts."""
        if os.path.exists(self.CONTRACT_STATE_FILE):
            with open(self.CONTRACT_STATE_FILE, "r") as f:
                self.contracts = json.load(f)
        else:
            self.contracts = {}
            
ifchain = IFChain()

def poh_generator():
    while True:
        ifchain.poh.generate_hash()
        time.sleep(1)

poh_thread = threading.Thread(target=poh_generator, daemon=True)
poh_thread.start()

schedule.every(365).days.do(ifchain.apply_inflation)

@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = []
    for block in ifchain.chain:
        chain_data.append(block.__dict__)
    return jsonify({
        "length": len(chain_data),
        "chain": chain_data,
        "contracts": ifchain.contracts  
    })

@app.route('/apply_inflation', methods=['POST'])
def trigger_inflation():
    if ifchain.apply_inflation():
        return jsonify({"message": "Inflation applied successfully."}), 200
    return jsonify({"error": "Inflation already applied for this year or not scheduled."}), 400

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    tx_data = request.get_json()
    required_fields = ["sender", "receiver", "amount", "token"]
    if not all(field in tx_data for field in required_fields):
        return "Invalid transaction data", 400
    if ifchain.add_new_transaction(tx_data):
        return "Transaction added to the pool", 201
    return "Transaction invalid", 400

@app.route('/mine', methods=['GET'])
def mine():
    result = ifchain.mine()
    if not result:
        return "No transactions to mine", 400
    return f"Block {result} is mined.", 200

@app.route('/freeze_token', methods=['POST'])
def freeze_token():
    data = request.get_json()
    if ifchain.freeze_token(data['token']):
        return jsonify({"message": f"{data['token']} is now frozen."}), 200
    return jsonify({"error": "Token freeze failed."}), 400

@app.route('/unfreeze_token', methods=['POST'])
def unfreeze_token():
    data = request.get_json()
    if ifchain.unfreeze_token(data['token']):
        return jsonify({"message": f"{data['token']} is now unfrozen."}), 200
    return jsonify({"error": "Token is not frozen or does not exist."}), 400

@app.route('/burn_tokens', methods=['POST'])
def burn_tokens():
    data = request.get_json()
    if ifchain.burn_tokens(data['token'], data['amount']):
        return jsonify({"message": f"{data['amount']} {data['token']} burned."}), 200
    return jsonify({"error": "Burn failed."}), 400

@app.route('/mint_tokens', methods=['POST'])
def mint_tokens():
    data = request.get_json()
    if ifchain.mint_tokens(data['token'], data['amount']):
        return jsonify({"message": f"{data['amount']} {data['token']} minted."}), 200
    return jsonify({"error": "Minting failed."}), 400
           
@app.route('/total_supply', methods=['GET'])
def get_total_supply():
    return jsonify({"total_supply": ifchain.get_total_supply()})
    
@app.route('/deploy_contract', methods=['POST'])
def api_deploy_contract():
    """API endpoint to deploy a smart contract."""
    data = request.get_json()
    if "contract_name" not in data or "contract_code" not in data:
        return jsonify({"error": "Missing contract name or code"}), 400

    if ifchain.deploy_contract(data["contract_name"], data["contract_code"]):
        return jsonify({"message": f"Contract {data['contract_name']} deployed."}), 200

    return jsonify({"error": "Contract deployment failed."}), 400

@app.route('/execute_contract', methods=['POST'])
def api_execute_contract():
    data = request.get_json()
    if "contract_name" not in data or "function_name" not in data or "params" not in data:
        return jsonify({"error": "Missing contract execution details"}), 400
    if ifchain.execute_contract(data["contract_name"], data["function_name"], data["params"]):
        return jsonify({"message": f"Function {data['function_name']} executed in {data['contract_name']}."}), 200
    return jsonify({"error": "Contract execution failed."}), 400
    
@app.route('/unconfirmed_transactions', methods=['GET'])
def get_unconfirmed_transactions():
    return jsonify({"unconfirmed_transactions": ifchain.unconfirmed_transactions})

@app.route('/contract_state/<contract_name>', methods=['GET'])
def get_contract_state(contract_name):
    """Fetch the state of a specific smart contract."""
    if contract_name in ifchain.contracts:
        return jsonify({
            "contract_name": contract_name,
            "state": ifchain.contracts[contract_name]["state"]
        }), 200
    return jsonify({"error": "Contract not found"}), 404
    
@app.route('/contracts', methods=['GET'])
def get_all_contracts():
    """Fetch a list of all deployed smart contracts."""
    return jsonify({"contracts": list(ifchain.contracts.keys())}), 200
  
@app.route('/contract/<contract_name>', methods=['DELETE'])
def delete_contract(contract_name):
    """Delete a specific smart contract."""
    if contract_name in ifchain.contracts:
        del ifchain.contracts[contract_name]  # Remove the contract from storage
        ifchain.save_contract_state()  # Save updated contract state
        return jsonify({"message": f"Contract {contract_name} deleted."}), 200
    return jsonify({"error": "Contract not found"}), 404
  
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
