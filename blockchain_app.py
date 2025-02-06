from flask import Flask, jsonify, request
import time
import hashlib
import json
import os
import schedule
import threading
from datetime import datetime
import requests

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
        self.hash = None  
        self.hash = self.compute_hash()  # 🔹 Compute hash after setting other attributes

    def to_dict(self, include_hash=True):
        """Convert block data to a dictionary, optionally including the hash."""
        block_dict = {
            "index": self.index,
            "timestamp": datetime.utcfromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "poh_hash": self.poh_hash,
            "nonce": self.nonce
        }
        if include_hash:
            block_dict["hash"] = self.hash
        return block_dict

    def compute_hash(self):
        """Compute SHA-256 hash of block data, excluding the hash field itself."""
        block_string = json.dumps(self.to_dict(include_hash=False), sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
        
class IFChain:
    difficulty = 2
    transaction_tax_rate = 0.03
    
    def __init__(self):
        self.CONTRACT_STATE_FILE = "contract_states.json"
        self.unconfirmed_transactions = []
        self.chain = []
        self.peers = set()
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
        self.sync_chain()

    def sync_chain(self):
        """Fetches the longest blockchain from peers and updates local chain if needed."""
        longest_chain = None
        max_length = len(self.chain)

        for peer in self.peers:
            try:
                response = requests.get(f"{peer}/chain")
                if response.status_code == 200:
                    peer_chain = response.json().get("chain", [])
                    peer_length = len(peer_chain)

                    if peer_length > max_length:
                        max_length = peer_length
                        longest_chain = peer_chain
            except requests.exceptions.RequestException:
                continue

        if longest_chain:
            self.chain = [Block(**block) for block in longest_chain]
            return True
        return False

    def register_peer(self, peer):
        """Registers a new node in the network."""
        if peer not in self.peers:
            self.peers.add(peer)
            return True
        return False

    def broadcast_transaction(self, tx_data):
        """Sends a new transaction to all peers."""
        for peer in self.peers:
            try:
                requests.post(f"{peer}/receive_transaction", json=tx_data, timeout=2)
            except requests.exceptions.RequestException:
                continue

    def broadcast_block(self, block_data):
        """Sends a newly mined block to all peers."""
        for peer in self.peers:
            try:
                requests.post(f"{peer}/receive_block", json=block_data, timeout=2)
            except requests.exceptions.RequestException:
                continue
        
    def create_genesis_block(self):
        genesis_block = Block(0, time.time(), [], "0", self.poh.current_hash)
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    def last_block(self):
        return self.chain[-1]

    def add_block(self, block, proof):
        """Adds a validated block to the chain and updates transaction confirmations."""
        previous_hash = self.last_block().hash if self.chain else "0"

        if previous_hash != block.previous_hash:
            return False  # Block invalid

        block.hash = proof
        self.chain.append(block)
    
        for prev_block in self.chain:
            for tx in prev_block.transactions:
                tx["block_confirmations"] += 1  # Increase confirmations

        return True

    def is_valid_proof(self, block, block_hash):
        return (block_hash.startswith('0' * IFChain.difficulty) and
                block_hash == block.compute_hash())

    def add_new_transaction(self, tx_data):
        """Adds a new transaction to the unconfirmed transaction pool."""
    
        required_fields = ["sender", "receiver", "amount", "token"]
        if not all(field in tx_data for field in required_fields):
            return False

        transaction = {
            "sender": tx_data["sender"],
            "receiver": tx_data["receiver"],
            "amount": tx_data["amount"],
            "token": tx_data["token"],
            "tax": round(tx_data["amount"] * 0.03, 2),
            "net_amount": round(tx_data["amount"] * 0.97, 2),
            "hash": hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest(),
            "timestamp": time.time(),
            "gas_fee": round(tx_data["amount"] * 0.001, 6),
            "tx_type": tx_data.get("tx_type", "transfer"),
            "block_confirmations": 0,
            "status": "pending",
            "signatures": []
        }

        self.unconfirmed_transactions.append(transaction)
        return True

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
        
    def deploy_contract(self, contract_name, contract_code, owner, expiration_time=None):
        """Deploy a contract with an optional expiration time."""
        if contract_name in self.contracts:
            return False

        wrapped_code = f"global state\nstate = {{}}\n{contract_code}"

        self.contracts[contract_name] = {
            "code": wrapped_code,
            "state": {},
            "state_versions": [],
            "owner": owner,
            "logs": [],
            "expiration": time.time() + expiration_time if expiration_time else None
        }
        return True

    def check_contract_validity(self, contract_name):
        """Check if a contract is still valid or expired."""
        if contract_name not in self.contracts:
            return False

        expiration = self.contracts[contract_name].get("expiration")
        if expiration and time.time() > expiration:
            return False  # Contract is expired

        return True

    def execute_contract(self, contract_name, function_name, params, sender):
        """Execute contract function with gas fee and improved error handling."""
        if contract_name not in self.contracts:
            return jsonify({"error": "Contract not found"}), 404

        contract_code = self.contracts[contract_name]["code"]
        contract_state = self.contracts[contract_name]["state"]

        if "logs" not in self.contracts[contract_name]:
            self.contracts[contract_name]["logs"] = []

        local_scope = {"state": contract_state}

        try:
            exec(contract_code, {}, local_scope)
        
            if function_name in local_scope and callable(local_scope[function_name]):
                gas_fee = CONTRACT_EXECUTION_FEE
                ifchain.get_wallet_balance(sender)  # Ensure sender has enough balance

                result = local_scope[function_name](**params)
                self.contracts[contract_name]["state"] = local_scope["state"]

                self.contracts[contract_name]["logs"].append({
                    "timestamp": time.time(),
                    "function": function_name,
                    "params": params,
                    "result": result,
                    "executed_by": sender,
                    "gas_fee": gas_fee
                })

                self.save_contract_state()
                return jsonify({
                    "message": f"Function {function_name} executed successfully.",
                    "result": result
                }), 200
        
            return jsonify({"error": "Function not found"}), 400

        except Exception as e:
            return jsonify({"error": f"Contract execution failed: {str(e)}"}), 400
    
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
            
    def mine(self):
        """Mine a new block if there are pending transactions and broadcast it."""
        if not self.unconfirmed_transactions:
            return "No transactions to mine"

        last_block = self.last_block()
        poh_hash = self.poh.current_hash

        transactions_to_add = self.unconfirmed_transactions.copy()

        new_block = Block(
            index=last_block.index + 1,
            timestamp=time.time(),
            transactions=transactions_to_add,
            previous_hash=last_block.hash,
            poh_hash=poh_hash
        )

        proof = self.proof_of_work(new_block)
        new_block.hash = proof
        self.add_block(new_block, proof)

        for tx in transactions_to_add:
            tx["status"] = "confirmed"
            tx["block_confirmations"] = 1  # First confirmation after mining

        self.unconfirmed_transactions = []
    
        self.broadcast_block(new_block.to_dict())

        return f"Block {new_block.index} is mined, contains {len(transactions_to_add)} transactions, and is broadcasted."
        
    def get_wallet_balance(self, wallet_address):
        """Retrieve the balance of a given wallet by summing all transactions."""
        balance = 0
        for block in self.chain:
            for tx in block.transactions:
                if tx["receiver"] == wallet_address:
                    balance += tx["net_amount"]  # Add received amount
                if tx["sender"] == wallet_address:
                    balance -= tx["amount"]  # Deduct sent amount
        return balance
        
    def execute_contract_call(self, contract_name, function_name, params):
        """Call a smart contract function without modifying blockchain state."""
        if contract_name not in self.contracts:
            return jsonify({"error": "Contract not found"}), 404

        contract_code = self.contracts[contract_name]["code"]
        contract_state = self.contracts[contract_name]["state"]

        local_scope = {"state": contract_state}

        try:
            exec(contract_code, {}, local_scope)

            if function_name in local_scope and callable(local_scope[function_name]):
                result = local_scope[function_name](**params)
                return jsonify({
                    "message": f"Function {function_name} executed successfully.",
                    "result": result
                }), 200

            return jsonify({"error": "Function not found"}), 400

        except Exception as e:
            return jsonify({"error": f"Contract call failed: {str(e)}"}), 400
            
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
    """Retrieve the full blockchain with formatted timestamps."""
    chain_data = [block.to_dict() for block in ifchain.chain]  
    return jsonify({
        "length": len(chain_data),
        "chain": chain_data
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

    if "contract_name" not in data or "contract_code" not in data or "owner" not in data:
        return jsonify({"error": "Missing contract name, code, or owner"}), 400

    contract_name = data["contract_name"]
    contract_code = data["contract_code"]
    owner = data["owner"]

    if contract_name in ifchain.contracts:
        return jsonify({"error": f"Contract {contract_name} already exists."}), 400

    if ifchain.deploy_contract(contract_name, contract_code, owner):
        return jsonify({"message": f"Contract {contract_name} deployed successfully by {owner}."}), 200

    return jsonify({"error": "Contract deployment failed."}), 400
    
@app.route('/execute_contract', methods=['POST'])
def api_execute_contract():
    data = request.get_json()
    if "contract_name" not in data or "function_name" not in data or "params" not in data:
        return jsonify({"error": "Missing contract execution details"}), 400
    if ifchain.execute_contract(data["contract_name"], data["function_name"], data["params"]):
        return jsonify({"message": f"Function {data['function_name']} executed in {data['contract_name']}."}), 200
    return jsonify({"error": "Contract execution failed."}), 400
 
@app.route('/update_contract', methods=['PUT'])
def update_contract():
    """Update a contract only if the request is from the owner."""
    data = request.get_json()

    if "contract_name" not in data or "new_code" not in data or "owner" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    contract_name = data["contract_name"]
    new_code = data["new_code"]
    owner = data["owner"]

    if contract_name not in ifchain.contracts:
        return jsonify({"error": "Contract not found"}), 404

    if ifchain.contracts[contract_name]["owner"] != owner:
        return jsonify({"error": "Unauthorized update"}), 403

    existing_state = ifchain.contracts[contract_name]["state"]
    ifchain.contracts[contract_name]["versions"].append({
        "code": ifchain.contracts[contract_name]["code"],
        "timestamp": time.time()
    })
    
    ifchain.contracts[contract_name]["code"] = new_code
    ifchain.contracts[contract_name]["state"] = existing_state
    ifchain.save_contract_state()

    return jsonify({"message": f"Contract {contract_name} updated successfully."}), 200
    
@app.route('/unconfirmed_transactions', methods=['GET'])
def get_unconfirmed_transactions():
    """Retrieve the list of pending transactions waiting to be mined."""
    pending_transactions = [
        {
            "sender": tx["sender"],
            "receiver": tx["receiver"],
            "amount": tx["amount"],
            "token": tx["token"],
            "tax": tx["tax"],
            "net_amount": tx["net_amount"],
            "timestamp": datetime.utcfromtimestamp(tx.get("timestamp", time.time())).strftime('%Y-%m-%d %H:%M:%S')
        }
        for tx in ifchain.unconfirmed_transactions
    ]

    return jsonify({
        "total_pending": len(pending_transactions),
        "pending_transactions": sorted(pending_transactions, key=lambda x: x["timestamp"])
    }), 200

@app.route('/contract_state/<contract_name>', methods=['GET'])
def get_contract_state(contract_name):
    """Fetch the state of a specific smart contract."""
    if contract_name in ifchain.contracts:
        return jsonify({
            "contract_name": contract_name,
            "state": ifchain.contracts[contract_name]["state"]
        }), 200
    return jsonify({"error": "Contract not found"}), 404
    
@app.route('/contract_versions/<contract_name>', methods=['GET'])
def get_contract_versions(contract_name):
    """Retrieve all past states of a contract with formatted timestamps."""
    if contract_name in ifchain.contracts and "state_versions" in ifchain.contracts[contract_name]:
        versions = [
            {
                "timestamp": datetime.utcfromtimestamp(v["timestamp"]).strftime('%Y-%m-%d %H:%M:%S'),
                "state": v["state"]
            }
            for v in ifchain.contracts[contract_name]["state_versions"]
        ]
        return jsonify({
            "contract_name": contract_name,
            "versions": versions
        }), 200
    return jsonify({"error": "No versions found for this contract"}), 404
    
@app.route('/contract_logs/<contract_name>', methods=['GET'])
def get_contract_logs(contract_name):
    """Fetch execution logs of a specific contract."""
    if contract_name in ifchain.contracts and "logs" in ifchain.contracts[contract_name]:
        return jsonify({
            "contract_name": contract_name,
            "logs": ifchain.contracts[contract_name]["logs"]
        }), 200
    return jsonify({"error": "No logs found for this contract"}), 404
    
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
  
@app.route('/block/<int:index>', methods=['GET'])
def get_block(index):
    """Fetch details of a specific block by index."""
    if index < len(ifchain.chain):
        return jsonify(ifchain.chain[index].__dict__), 200
    return jsonify({"error": "Block not found"}), 404
    
@app.route('/all_transactions', methods=['GET'])
def fetch_all_transactions():
    """Retrieve all transactions in the blockchain."""
    transactions = []
    for block in ifchain.chain:
        transactions.extend(block.transactions)

    return jsonify({
        "total_transactions": len(transactions),
        "transactions": transactions
    }), 200
    
@app.route('/wallet_transactions/<wallet_address>', methods=['GET'])
def get_wallet_transactions(wallet_address):
    """Retrieve all transactions involving a specific wallet address with filtering options."""
    
    token_filter = request.args.get('token')
    transaction_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    transactions = []

    for block in ifchain.chain:
        block_time = datetime.utcfromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        block_timestamp = datetime.strptime(block_time, '%Y-%m-%d %H:%M:%S')

        for tx in block.transactions:
            
            if wallet_address not in [tx["sender"], tx["receiver"]]:
                continue
            
            if token_filter and tx["token"] != token_filter:
                continue
            
            if transaction_type == "sent" and tx["sender"] != wallet_address:
                continue
            if transaction_type == "received" and tx["receiver"] != wallet_address:
                continue
            
            if start_date and end_date:
                try:
                    start_timestamp = datetime.strptime(start_date, "%Y-%m-%d")
                    end_timestamp = datetime.strptime(end_date, "%Y-%m-%d")
                    if not (start_timestamp <= block_timestamp <= end_timestamp):
                        continue
                except ValueError:
                    return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
           
            transactions.append({
                "transaction_hash": tx["hash"],
                "block_index": block.index,
                "timestamp": block_time,
                "sender": tx["sender"],
                "receiver": tx["receiver"],
                "amount": tx["amount"],
                "token": tx["token"],
                "tax": tx["tax"],
                "net_amount": tx["net_amount"]
            })

    return jsonify({
        "wallet_address": wallet_address,
        "total_transactions": len(transactions),
        "transactions": transactions
    }), 200
    
@app.route('/wallet_balance/<wallet_address>', methods=['GET'])
def get_wallet_balance(wallet_address):
    """Retrieve the balance of tokens for a specific wallet."""
    balance = {}
    
    for block in ifchain.chain:
        for tx in block.transactions:
            token = tx["token"]
            amount = tx["net_amount"]
            
            if tx["receiver"] == wallet_address:
                balance[token] = balance.get(token, 0) + amount
            if tx["sender"] == wallet_address:
                balance[token] = balance.get(token, 0) - amount

    return jsonify({"wallet_address": wallet_address, "balance": balance}), 200
    
@app.route('/search_transactions', methods=['GET'])
def search_transactions():
    """Search transactions by sender, receiver, token type, or all."""
    sender = request.args.get('sender')
    receiver = request.args.get('receiver')
    token = request.args.get('token')

    matching_transactions = []

    for block in ifchain.chain:
        for tx in block.transactions:
            if ((not sender or tx["sender"] == sender) and
                (not receiver or tx["receiver"] == receiver) and
                (not token or tx["token"] == token)):
                matching_transactions.append(tx)

    return jsonify({
        "total_matches": len(matching_transactions),
        "transactions": matching_transactions
    }), 200
    
@app.route('/search_transaction_by_hash', methods=['GET'])
def search_transaction_by_hash():
    """Search for a transaction using its unique hash."""
    tx_hash = request.args.get('hash')

    if not tx_hash:
        return jsonify({"error": "Transaction hash is required"}), 400

    for block in ifchain.chain:
        for tx in block.transactions:
            if "hash" in tx and tx["hash"] == tx_hash:
                return jsonify({
                    "transaction": tx,
                    "block_index": block.index,
                    "timestamp": datetime.utcfromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    "status": tx["status"],
                    "confirmations": tx["block_confirmations"],
                    "gas_fee": tx["gas_fee"],
                    "type": tx["tx_type"],
                    "signatures": tx["signatures"]
                }), 200

    return jsonify({"error": "Transaction not found"}), 404
    
@app.route('/search_transactions_by_date', methods=['GET'])
def search_transactions_by_date():
    """Search for transactions within a date range."""
    start_date = request.args.get('start_date')  # Expected format: YYYY-MM-DD
    end_date = request.args.get('end_date')  # Expected format: YYYY-MM-DD

    if not start_date or not end_date:
        return jsonify({"error": "Both start_date and end_date are required"}), 400

    try:
        start_timestamp = datetime.strptime(start_date, "%Y-%m-%d").timestamp()
        end_timestamp = datetime.strptime(end_date, "%Y-%m-%d").timestamp()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    matched_transactions = []

    for block in ifchain.chain:
        if start_timestamp <= block.timestamp <= end_timestamp:
            for tx in block.transactions:
                matched_transactions.append({
                    "transaction": tx,
                    "block_index": block.index,
                    "timestamp": datetime.utcfromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                })

    return jsonify({
        "total_matches": len(matched_transactions),
        "transactions": matched_transactions
    }), 200
    
@app.route('/search_transactions_by_amount', methods=['GET'])
def search_transactions_by_amount():
    """Search for transactions within a specified amount range."""
    min_amount = request.args.get('min_amount', type=float, default=0)
    max_amount = request.args.get('max_amount', type=float, default=float('inf'))

    matched_transactions = []

    for block in ifchain.chain:
        for tx in block.transactions:
            if min_amount <= tx["amount"] <= max_amount:
                matched_transactions.append({
                    "transaction": tx,
                    "block_index": block.index,
                    "timestamp": datetime.utcfromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                })

    return jsonify({
        "total_matches": len(matched_transactions),
        "transactions": matched_transactions
    }), 200
    
@app.route('/search_transactions_advanced', methods=['GET'])
def search_transactions_advanced():
    """Search transactions using multiple filters."""
    sender = request.args.get('sender')
    receiver = request.args.get('receiver')
    token = request.args.get('token')
    min_amount = request.args.get('min_amount', type=float, default=0)
    max_amount = request.args.get('max_amount', type=float, default=float('inf'))
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    block_number = request.args.get('block_number', type=int)

    matched_transactions = []

    for block in ifchain.chain:
        block_time = datetime.utcfromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S')

        if block_number is not None and block.index != block_number:
            continue

        if start_date and end_date:
            try:
                start_timestamp = datetime.strptime(start_date, "%Y-%m-%d").timestamp()
                end_timestamp = datetime.strptime(end_date, "%Y-%m-%d").timestamp()
                if not (start_timestamp <= block.timestamp <= end_timestamp):
                    continue
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

        for tx in block.transactions:
            if sender and tx["sender"] != sender:
                continue
            if receiver and tx["receiver"] != receiver:
                continue
            if token and tx["token"] != token:
                continue
            if not (min_amount <= tx["amount"] <= max_amount):
                continue

            matched_transactions.append({
                "transaction": tx,
                "block_index": block.index,
                "timestamp": block_time
            })

    return jsonify({
        "total_matches": len(matched_transactions),
        "transactions": matched_transactions
    }), 200
    
@app.route('/block/<block_identifier>', methods=['GET'])
def get_block_details(block_identifier):
    """
    Retrieve block details by either block index or block hash.
    """
    
    if block_identifier.isdigit():
        block_index = int(block_identifier)
        block = next((b for b in ifchain.chain if b.index == block_index), None)
    else:
        block_hash = block_identifier
        block = next((b for b in ifchain.chain if b.hash == block_hash), None)

    if block is None:
        return jsonify({"error": "Block not found"}), 404

    return jsonify(block.to_dict()), 200
    
@app.route('/debug_hashes', methods=['GET'])
def debug_hashes():
    """
    Debugging route to check stored hashes vs computed ones.
    """
    hashes = []
    for block in ifchain.chain:
        hashes.append({
            "index": block.index,
            "stored_hash": block.hash,
            "computed_hash": block.compute_hash()
        })
    return jsonify(hashes), 200
    
@app.route('/pending_transactions', methods=['GET'])
def get_pending_transactions():
    """Retrieve the list of unconfirmed transactions waiting to be mined."""
    return jsonify({
        "total_pending": len(ifchain.unconfirmed_transactions),
        "pending_transactions": ifchain.unconfirmed_transactions
    }), 200
    
@app.route('/blockchain_overview', methods=['GET'])
def blockchain_overview():
    """Provides an overview of the blockchain status."""
    
    total_blocks = len(ifchain.chain)
    total_transactions = sum(len(block.transactions) for block in ifchain.chain)
    total_wallets = len(set(tx["sender"] for block in ifchain.chain for tx in block.transactions) |
                        set(tx["receiver"] for block in ifchain.chain for tx in block.transactions))
    total_contracts = len(ifchain.contracts)
    pending_transactions = len(ifchain.unconfirmed_transactions)

    latest_block = ifchain.chain[-1].to_dict() if ifchain.chain else None

    return jsonify({
        "total_blocks": total_blocks,
        "total_transactions": total_transactions,
        "total_wallets": total_wallets,
        "total_smart_contracts": total_contracts,
        "pending_transactions": pending_transactions,
        "latest_block": latest_block
    }), 200
    
@app.route('/block/<block_hash>', methods=['GET'])
def get_block_by_hash(block_hash):
    """Retrieve a block by its hash."""
    for block in ifchain.chain:
        if block.compute_hash() == block_hash:
            return jsonify(block.to_dict()), 200
    return jsonify({"error": "Block not found"}), 404
    
@app.route('/register_peer', methods=['POST'])
def register_peer():
    """Registers a new peer node."""
    data = request.get_json()
    peer = data.get("peer")

    if not peer:
        return jsonify({"error": "Peer address required"}), 400

    ifchain.register_peer(peer)
    return jsonify({"message": f"Peer {peer} added successfully", "peers": list(ifchain.peers)}), 200

@app.route('/peers', methods=['GET'])
def get_peers():
    """Returns the list of registered peers."""
    return jsonify({"peers": list(ifchain.peers)}), 200

@app.route('/receive_block', methods=['POST'])
def receive_block():
    """Receives and validates a new block from peers."""
    block_data = request.get_json()
    new_block = Block(**block_data)

    if ifchain.add_block(new_block, new_block.hash):
        return jsonify({"message": "Block accepted"}), 200
    return jsonify({"error": "Block rejected"}), 400

@app.route('/receive_transaction', methods=['POST'])
def receive_transaction():
    """Receives and stores a new transaction from peers."""
    tx_data = request.get_json()

    if ifchain.add_new_transaction(tx_data):
        return jsonify({"message": "Transaction accepted"}), 200
    return jsonify({"error": "Invalid transaction"}), 400
    
@app.route('/sync_chain', methods=['GET'])
def sync_chain():
    """API endpoint to synchronize blockchain with peers."""
    if ifchain.sync_chain():
        return jsonify({"message": "Blockchain synchronized successfully."}), 200
    return jsonify({"error": "No longer chain found or sync failed."}), 400
    
@app.route('/execute_contract_call', methods=['GET'])
def execute_contract_call():
    """Execute a smart contract function without modifying state (read-only calls)."""
    contract_name = request.args.get('contract_name')
    function_name = request.args.get('function_name')

    if not contract_name or not function_name:
        return jsonify({"error": "Missing contract_name or function_name"}), 400

    if contract_name not in ifchain.contracts:
        return jsonify({"error": "Contract not found"}), 404

    contract_code = ifchain.contracts[contract_name]["code"]
    contract_state = ifchain.contracts[contract_name]["state"]

    local_scope = {"state": contract_state}
    exec(contract_code, {}, local_scope)

    if function_name in local_scope and callable(local_scope[function_name]):
        result = local_scope[function_name]()
        return jsonify({"contract": contract_name, "function": function_name, "result": result}), 200

    return jsonify({"error": f"Function {function_name} not found in contract {contract_name}"}), 404
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
