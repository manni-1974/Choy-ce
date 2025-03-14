from flask import Flask, jsonify, request
import time
import hashlib
import json
import os
import schedule
import threading
from datetime import datetime
import requests
from ecdsa import SECP256k1, SigningKey

app = Flask(__name__)

ifchain = None

def get_ifchain_instance():
    """Ensures a single instance of the blockchain is used."""
    global ifchain
    if ifchain is None:
        ifchain = IFChain()  
    return ifchain

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
    def __init__(self, index, timestamp, transactions, previous_hash, poh_hash, nonce=0, hash=None):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.poh_hash = poh_hash
        self.nonce = nonce
        self.hash = hash if hash else self.compute_hash()
        
    def to_dict(self, include_hash=True):
        """Convert block data to a dictionary, optionally including the hash."""
        block_dict = {
            "index": self.index,
            "timestamp": (
                datetime.utcfromtimestamp(int(self.timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                if isinstance(self.timestamp, (int, float)) else self.timestamp
            ),
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
    GAS_FEE_PER_TRANSACTION = 0.001
    GAS_FEE_PER_CONTRACT_EXECUTION = 0.002
    
    def __init__(self, port):
        self.port = port
        self.chain_id = "1985"
        self.CONTRACT_STATE_FILE = "contract_states.json"
        self.BLOCKCHAIN_FILE = "blockchain.json"
        self.PENDING_TRANSACTIONS_FILE = "pending_transactions.json"
        self.unconfirmed_transactions = []
        self.chain = []
        self.peers = set()
        self.poh = PoH()
        self.token_supply = 500_000_000
        self.frozen_tokens = {}
        self.burned_tokens = 0
        self.inflation_schedule = self.generate_inflation_schedule()
        self.applied_inflation_years = set()
        self.minted_tokens = {}
        self.contracts = {}
        self.wallet_balances = {}
        self.gas_fee = 0.005

        self.load_wallet_balances()
        self.load_unconfirmed_transactions()
        self.load_contract_state()
        self.load_peers()
        
        # ✅ Prevent Genesis Block Overwriting
        if not os.path.exists(self.BLOCKCHAIN_FILE) or os.stat(self.BLOCKCHAIN_FILE).st_size == 0:
            print("DEBUG: No blockchain file found, creating genesis block.")
            self.create_genesis_block()
            self.save_blockchain_state()  # Save the new blockchain file
        else:
            print("DEBUG: Blockchain file exists, loading from storage.")
            self.load_blockchain_state()

        self.sync_chain()
     
    def sync_chain(self):
        """Fetches the longest blockchain from peers and updates local chain if needed."""
        longest_chain = None
        max_length = len(self.chain)

        print(f"DEBUG: Syncing with peers {self.peers}")

        for peer in self.peers:
            try:
                response = requests.get(f"{peer}/chain", timeout=3)  # Ensure we get a response quickly
                if response.status_code == 200:
                    peer_chain = response.json().get("chain", [])
                    peer_chain_id = response.json().get("chain_id", "")  # Get peer's chain ID

                    # Validate Chain ID to ensure you are connecting to the correct blockchain
                    if peer_chain_id != self.chain_id:
                        print(f"ERROR: Peer {peer} has a different Chain ID. Sync aborted.")
                        continue

                    peer_length = len(peer_chain)
                    print(f"DEBUG: Peer {peer} has chain length {peer_length}")

                    # If the peer's chain is longer, update our local copy
                    if peer_length > max_length:
                        max_length = peer_length
                        longest_chain = peer_chain
            except requests.exceptions.RequestException as e:
                print(f"ERROR: Failed to connect to {peer} - {e}")

        if longest_chain:
            # Convert JSON blocks to Block objects to update local chain
            self.chain = [Block(**block) for block in longest_chain]
            self.save_blockchain_state()
            print(f"DEBUG: Synced to a longer chain of length {max_length}")
            return {"message": "Blockchain synchronized successfully."}, 200

        print("DEBUG: No valid longer chain found. Sync skipped.")
        return {"error": "No longer chain found or sync failed."}, 400


    def validate_chain(self, chain):
        """Ensures the chain received from peers is valid before replacing local chain."""
        for i in range(1, len(chain)):
            prev_block = chain[i - 1]
            curr_block = chain[i]

            # Validate hash link
            if curr_block["previous_hash"] != prev_block["hash"]:
                print(f"ERROR: Invalid chain link at index {curr_block['index']}")
                return False

            # Validate proof of work
            if not curr_block["hash"].startswith("0" * IFChain.difficulty):
                print(f"ERROR: Invalid proof of work at index {curr_block['index']}")
                return False

        return True

    def generate_wallet(self):
        """Generates a new wallet with private and public keys."""
        sk = SigningKey.generate(curve=SECP256k1)  # Generate private key
        pk = sk.get_verifying_key()  # Generate public key

        private_key = sk.to_string().hex()  # Convert private key to hex string
        public_key = pk.to_string().hex()  # Convert public key to hex string

        # Optionally save the wallet and return its information
        wallet_address = public_key[:40]  # This is just a simple address format. You can adjust based on your needs.

        # Store wallet balances with a default value (e.g., 0 balance for a new wallet)
        if wallet_address not in self.wallet_balances:
            self.wallet_balances[wallet_address] = {"IFC": 0}  # Initialize balance for the wallet

        self.save_wallet_balances()  # Save updated wallet balances to file

        return {"private_key": private_key, "public_key": public_key, "address": wallet_address}
        
    def save_peers(self):
        """Saves the peer list to a file for persistence."""
        with open("peers.json", "w") as f:
            json.dump(list(self.peers), f)
        print("Peers saved successfully.")

    def load_peers(self):
        """Loads peers from a file on startup."""
        if os.path.exists("peers.json"):
            with open("peers.json", "r") as f:
                self.peers = set(json.load(f))
            print(f"Loaded peers from file: {self.peers}")

            # Ensure the node does not register itself as a peer
            self_address = f"http://127.0.0.1:{self.port}"
            if self_address in self.peers:
                self.peers.remove(self_address)

        else:
            self.peers = set()
    
    def register_peer(self, peer):
        """Registers a new node in the network and immediately saves it to file."""
        self_address = f"http://127.0.0.1:{self.port}"  # Get own address

        if peer == self_address:
            print("DEBUG: Node tried to register itself. Ignoring.")
            return False  # Prevent self-registration

        if peer not in self.peers:
            self.peers.add(peer)
            self.save_peers()  # Save peers to file
            print(f"DEBUG: Registered peer {peer}")

            # 🔹 Notify the new peer about this node
            try:
                requests.post(f"{peer}/register_peer", json={"peer": self_address}, timeout=5)
                print(f"DEBUG: Notified {peer} to register this node as a peer.")
            except requests.exceptions.RequestException as e:
                print(f"WARNING: Failed to notify {peer}. Error: {e}")

            return True
        return False


    def broadcast_transaction(self, tx_data):
        """Sends a new transaction to all peers."""
        print(f"Broadcasting transaction to peers: {self.peers}")  # Debugging Log
        for peer in self.peers:
            try:
                response = requests.post(f"{peer}/receive_transaction", json=tx_data, timeout=2)
                print(f"Transaction sent to {peer} Status: {response.status_code} Response: {response.text}")  # Debugging Log
            except requests.exceptions.RequestException as e:
                print(f"Failed to send transaction to {peer}: {e}")  # Debugging Log


    def broadcast_block(self, block_data):
        """Sends a newly mined block to all peers."""
        print(f"Broadcasting block {block_data['index']} to peers: {self.peers}")  # Debugging Log

        for peer in self.peers:
            try:
                response = requests.post(f"{peer}/receive_block", json=block_data, timeout=5)
                if response.status_code == 200:
                    print(f"Block {block_data['index']} successfully sent to {peer} ✅")
                else:
                    print(f"Peer {peer} rejected block {block_data['index']} ❌ Status: {response.status_code} Response: {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"Failed to send block {block_data['index']} to {peer}: {e}")  # Debugging Log

        
    def create_genesis_block(self):
        genesis_block = Block(0, time.time(), [], "0", self.poh.current_hash)
        genesis_block.hash = genesis_block.compute_hash()
        genesis_block.chain_id = self.chain_id  # Attach Chain ID to the genesis block
        self.chain.append(genesis_block)
        self.save_blockchain_state()
        
    def load_blockchain_state(self):
        if os.path.exists(self.BLOCKCHAIN_FILE):
            try:
                print("DEBUG: Loading blockchain from file...")
                with open(self.BLOCKCHAIN_FILE, "r") as f:
                    chain_data = json.load(f)

                if not chain_data:
                    print("WARNING: blockchain.json is empty!")
                    return

                self.chain = [Block(
                    index=block["index"],
                    timestamp=block["timestamp"],
                    transactions=block["transactions"],
                    previous_hash=block["previous_hash"],
                    poh_hash=block["poh_hash"],
                    nonce=block["nonce"],
                    hash=block["hash"]
                ) for block in chain_data]

                print(f"DEBUG: Loaded {len(self.chain)} blocks from file.")

            except json.JSONDecodeError:
                print("ERROR: Corrupted blockchain file! Resetting to genesis block.")
                self.chain = [self.create_genesis_block()]
        else:
            print("WARNING: No blockchain file found. Creating new genesis block.")
            self.chain = [self.create_genesis_block()]

    def save_blockchain_state(self):
        with open(self.BLOCKCHAIN_FILE, "w") as f:
            json.dump([block.to_dict() for block in self.chain], f)
        print("Blockchain state saved")
        
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
        print(f"Received transaction: {tx_data}")  # Debugging Log

        required_fields = ["sender", "receiver", "amount", "token"]
        if not all(field in tx_data for field in required_fields):
            print("Transaction failed: Missing required fields.")
            return False

        sender = tx_data["sender"]
        receiver = tx_data["receiver"]
        amount = tx_data["amount"]
        token = tx_data["token"]
        
        gas_fee = amount * self.gas_fee
        net_amount = amount - gas_fee

        sender_balance = self.get_wallet_balance(sender).get("balance", {}).get(token, 0)

        if sender_balance < (amount + gas_fee):
            print(f"Transaction failed: Insufficient balance for {sender}. Available: {sender_balance}, Required: {amount + gas_fee}")
            return False

        transaction = {
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "token": token,
            "gas_fee": gas_fee,
            "net_amount": net_amount,
            "hash": hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest(),
            "timestamp": time.time(),
            "tx_type": "transfer",
            "block_confirmations": 0,
            "status": "pending",
            "signatures": []
        }

        self.unconfirmed_transactions.append(transaction)
        self.save_unconfirmed_transactions()
        
        print(f"Transaction added successfully: {transaction}")
        print(f"DEBUG: Current Unconfirmed Transactions: {self.unconfirmed_transactions}")
        
        # ✅ New Debug Logs to Ensure Transaction is Broadcasted
        print("Now broadcasting transaction to peers...")
        self.broadcast_transaction(transaction)

        return True

            
    def force_add_balance(self, wallet_address, token, amount):
        """Forcefully add balance to a wallet and create a mint transaction."""
        
        if wallet_address not in self.wallet_balances:
            self.wallet_balances[wallet_address] = {}

        try:
            amount = float(amount)
        except ValueError:
            print(f"Error: Amount must be a valid number, received {amount}")
            return {"error": "Invalid amount format"}

        # Check the current balance before updating
        current_balance = self.wallet_balances[wallet_address].get(token, 0)
        print(f"DEBUG: Current balance of {wallet_address} {token}: {current_balance}")

        # Update the balance
        self.wallet_balances[wallet_address][token] = current_balance + amount
        print(f"DEBUG: New balance of {wallet_address} {token}: {self.wallet_balances[wallet_address][token]}")

        # Save balance persistently
        self.save_wallet_balances()

        new_tx = {
            "sender": "SYSTEM",
            "receiver": wallet_address,
            "amount": amount,
            "token": token,
            "gas_fee": 0,  # No gas fee for minting
            "net_amount": amount,
            "hash": hashlib.sha256(f"mint-{wallet_address}-{time.time()}".encode()).hexdigest(),
            "timestamp": time.time(),
            "tx_type": "mint",
            "block_confirmations": 0,  # It is not yet mined
            "status": "pending",
            "signatures": []
        }

        self.unconfirmed_transactions.append(new_tx)
        print(f"DEBUG: Mint transaction added to pool: {new_tx['hash']}")

        return {"message": f"{amount} {token} added to {wallet_address}"}
        
    def save_pending_transactions(self):
        """Save unconfirmed transactions to a file for persistence."""
        with open("pending_transactions.json", "w") as f:
            json.dump(self.unconfirmed_transactions, f)
        print("DEBUG: Pending transactions saved.")

    def load_pending_transactions(self):
        """Load unconfirmed transactions from a file."""
        if os.path.exists("pending_transactions.json"):
            with open("pending_transactions.json", "r") as f:
                try:
                    self.unconfirmed_transactions = json.load(f)
                except json.JSONDecodeError:
                    print("ERROR: Corrupted pending transactions file, resetting.")
                    self.unconfirmed_transactions = []
        else:
            self.unconfirmed_transactions = []
        print("DEBUG: Pending transactions loaded.")
        
    def save_unconfirmed_transactions(self):
        """Save unconfirmed transactions to a file to persist across restarts."""
        with open(self.PENDING_TRANSACTIONS_FILE, "w") as f:
            json.dump(self.unconfirmed_transactions, f)
        print("DEBUG: Saved pending transactions to file.")

    def load_unconfirmed_transactions(self):
        """Load unconfirmed transactions from file at startup."""
        if os.path.exists(self.PENDING_TRANSACTIONS_FILE):
            try:
                with open(self.PENDING_TRANSACTIONS_FILE, "r") as f:
                    self.unconfirmed_transactions = json.load(f)
                print("DEBUG: Loaded pending transactions from file.")
            except json.JSONDecodeError:
                print("ERROR: Corrupt pending transactions file! Resetting list.")
                self.unconfirmed_transactions = []
        else:
            self.unconfirmed_transactions = []

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
        if not hasattr(self, "burned_tokens"):
            self.burned_tokens = {}

        if token not in self.minted_tokens:
            print(f"Burn failed: {token} does not exist in minted tokens.")
            return False

        if amount > self.minted_tokens[token]:
            print(f"Burn failed: Not enough {token} to burn. Available: {self.minted_tokens[token]}, Requested: {amount}")
            return False

        self.minted_tokens[token] -= amount
        self.token_supply -= amount

        if token not in self.burned_tokens:
            self.burned_tokens[token] = 0
        self.burned_tokens[token] += amount

        print(f"Burn successful: {amount} {token} burned. New Supply: {self.token_supply}")
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
        """Deploy a smart contract with ownership and optional expiration."""
        if contract_name in self.contracts:
            return False  # Contract already exists

        wrapped_code = f"global state\nstate = {{}}\n{contract_code}"

        self.contracts[contract_name] = {
            "code": wrapped_code,
            "state": {},
            "state_versions": [],
            "owner": owner,  # Owner's wallet address
            "logs": [],
            "expiration": time.time() + expiration_time if expiration_time else None  # Optional expiration
        }

        self.save_contract_state()
        return True

    def check_contract_validity(self, contract_name):
        """Check if a contract is still valid or expired."""
        if contract_name not in self.contracts:
            return False

        expiration = self.contracts[contract_name].get("expiration")
        if expiration and time.time() > expiration:
            return False  # Contract is expired

        return True

    def execute_contract(self, contract_name, function_name, params, sender=None, readonly=False):
        """Execute or call a smart contract function.

        - If `readonly=True`, it will execute the function **without modifying state** or charging gas.
        - If `readonly=False`, it will execute **with state modification** and charge gas fees.
        """

        if contract_name not in self.contracts:
            return jsonify({"error": "Contract not found"}), 404

        contract_data = self.contracts[contract_name]
        contract_code = contract_data["code"]
        contract_state = contract_data["state"]

        if "logs" not in contract_data:
            contract_data["logs"] = []

        local_scope = {"state": contract_state}

        try:
            exec(contract_code, {}, local_scope)

            if function_name in local_scope and callable(local_scope[function_name]):
                if readonly:
                    result = local_scope[function_name](**params)
                    return jsonify({
                        "message": f"Function {function_name} executed successfully (readonly).",
                        "result": result
                    }), 200

                # Gas fee calculation
                gas_fee = self.GAS_FEE_PER_CONTRACT_EXECUTION
                sender_balance = self.get_wallet_balance(sender).get("balance", {}).get("IFC", 0)

                if sender_balance < gas_fee:
                    return jsonify({"error": "Insufficient balance for gas fee"}), 400

                # Deduct gas fees and modify blockchain transactions
                gas_transaction = {
                    "sender": sender,
                    "receiver": "MINER_POOL",
                    "amount": gas_fee,
                    "token": "IFC",
                    "gas_fee": gas_fee,
                    "net_amount": -gas_fee,
                    "hash": hashlib.sha256(f"gas-{sender}-{time.time()}".encode()).hexdigest(),
                    "timestamp": time.time(),
                    "tx_type": "gas_fee",
                    "block_confirmations": 0,
                    "status": "pending",
                    "signatures": []
                }

                # Add gas fee transaction to pending transactions
                self.unconfirmed_transactions.append(gas_transaction)

                # Execute the contract function with state modification
                result = local_scope[function_name](**params)
                contract_data["state"] = local_scope["state"]

                # Log contract execution
                contract_data["logs"].append({
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
                    "result": result,
                    "gas_fee_deducted": gas_fee
                }), 200

            return jsonify({"error": "Function not found in contract"}), 400

        except Exception as e:
            return jsonify({"error": f"Contract execution failed: {str(e)}"}), 400
            
    def save_contract_state(self):
        """Save all smart contract states to a file for persistence."""
        try:
            with open(self.CONTRACT_STATE_FILE, "w") as f:
                json.dump(self.contracts, f, indent=4)
        except Exception as e:
            print(f"Error saving contract state: {str(e)}")

    def load_contract_state(self):
        """Load contract states from a file when the blockchain starts."""
        if os.path.exists(self.CONTRACT_STATE_FILE):
            try:
                with open(self.CONTRACT_STATE_FILE, "r") as f:
                    self.contracts = json.load(f)
                    
                    for contract in self.contracts.values():
                        contract.setdefault("state", {})
                        contract.setdefault("state_versions", [])
                        contract.setdefault("logs", [])
                        contract.setdefault("owner", None)
                        contract.setdefault("expiration", None)
            except json.JSONDecodeError:
                print("Error: Corrupted contract state file. Resetting contracts.")
                self.contracts = {}
        else:
            self.contracts = {}
            
    def mine(self, miner_wallet):
        """Mine a new block if there are pending transactions and reward the miner."""
        
        print("DEBUG: Mining started...")
        print("DEBUG: Current pending transactions BEFORE mining:", self.unconfirmed_transactions)  # 🔍 Debugging

        if not self.unconfirmed_transactions:
            print("DEBUG: No transactions available to mine.")
            return "No transactions to mine"

        last_block = self.last_block()
        poh_hash = self.poh.current_hash  # ✅ Capture current PoH hash

        transactions_to_add = self.unconfirmed_transactions.copy()
        print(f"DEBUG: Transactions being added to block: {transactions_to_add}")

        gas_collected = 0

        for tx in transactions_to_add:
            tx["status"] = "confirmed"
            tx["block_confirmations"] = 1
            gas_collected += tx.get("gas_fee", 0)

        new_block = Block(
            index=last_block.index + 1,
            timestamp=time.time(),
            transactions=transactions_to_add,
            previous_hash=last_block.hash,
            poh_hash=poh_hash  # ✅ Ensure PoH hash is sent with the block
        )

        proof = self.proof_of_work(new_block)
        new_block.hash = proof
        self.add_block(new_block, proof)

        print(f"DEBUG: Mined Block {new_block.index} - Hash: {new_block.hash}")
        print(f"DEBUG: Total Blocks in Memory after mining: {len(self.chain)}")

        self.unconfirmed_transactions = []  # Clear mined transactions
        self.save_blockchain_state()

        print("DEBUG: Current pending transactions AFTER mining:", self.unconfirmed_transactions)  # 🔍 Debugging

        # ✅ Auto-sync: Broadcast the new block to peers
        self.broadcast_block(new_block.__dict__)  # ✅ Convert to dictionary

        return f"Block {new_block.index} mined with {len(transactions_to_add)} transactions."

   
    def get_wallet_balance(self, wallet_address):
        """Retrieve the balance of tokens for a specific wallet from the chain and saved balances."""

        balance = {}

        print(f"Fetching balance for {wallet_address} from stored wallet balances and blockchain...")

        # ✅ Step 1: Check saved wallet balances first
        if wallet_address in self.wallet_balances:
            balance = self.wallet_balances[wallet_address].copy()  # Get saved balances
            print(f"Loaded stored balance for {wallet_address}: {balance}")

        # ✅ Step 2: Check confirmed transactions in the blockchain
        for block in self.chain:
            print(f"Checking block {block.index}...")
            for tx in block.transactions:
                token = tx.get("token", "IFC")  # Default to IFC if token key is missing
                net_amount = tx.get("net_amount", tx.get("amount", 0))  # Prevent KeyError

                if tx.get("receiver") == wallet_address:
                    balance[token] = balance.get(token, 0) + net_amount
                    print(f"Adding {net_amount} {token} to {wallet_address} from confirmed transaction.")

                if tx.get("sender") == wallet_address:
                    balance[token] = balance.get(token, 0) - tx.get("amount", 0)  # Prevent KeyError
                    print(f"Subtracting {tx.get('amount', 0)} {token} from {wallet_address} (sent transaction).")

        # ✅ Step 3: Check pending (unconfirmed) transactions
        for tx in self.unconfirmed_transactions:
            print("Checking unconfirmed transactions...")
            token = tx.get("token", "IFC")
            net_amount = tx.get("net_amount", tx.get("amount", 0))  # Prevent KeyError

            if tx.get("receiver") == wallet_address:
                balance[token] = balance.get(token, 0) + net_amount
                print(f"Adding {net_amount} {token} from unconfirmed transaction.")

            if tx.get("sender") == wallet_address:
                balance[token] = balance.get(token, 0) - tx.get("amount", 0)  # Prevent KeyError
                print(f"Subtracting {tx.get('amount', 0)} {token} from unconfirmed transaction.")

        # ✅ Step 4: Round final balance for better readability
        balance = {token: round(amount, 6) for token, amount in balance.items()}

        print(f"Final balance for {wallet_address}: {balance}")

        return {"wallet_address": wallet_address, "balance": balance}
        
    def load_wallet_balances(self):
        """Load wallet balances from a JSON file."""
        if os.path.exists("wallet_balances.json"):
            try:
                with open("wallet_balances.json", "r") as f:
                    self.wallet_balances = json.load(f)
                print(f"DEBUG: Loaded wallet balances: {self.wallet_balances}")
            except json.JSONDecodeError:
                print("ERROR: Corrupted wallet balance file. Resetting balances.")
                self.wallet_balances = {}
        else:
            self.wallet_balances = {}
            print("DEBUG: No wallet balances file found. Initialized empty balances.")

    def save_wallet_balances(self):
        """Save wallet balances to a JSON file for persistence."""
        try:
            with open("wallet_balances.json", "w") as f:
                json.dump(self.wallet_balances, f, indent=4)
            print(f"DEBUG: Wallet balances saved successfully: {self.wallet_balances}")
        except Exception as e:
            print(f"ERROR: Failed to save wallet balances - {e}")
                        
    def update_contract(self, contract_name, new_code, sender):
        """Update an existing smart contract with ownership verification."""
        if contract_name not in self.contracts:
            return {"error": "Contract not found"}, 404

        if self.contracts[contract_name]["owner"] != sender:
            return {"error": "Unauthorized: Only the contract owner can update it"}, 403

        existing_state = self.contracts[contract_name]["state"]
    
        if "versions" not in self.contracts[contract_name]:
            self.contracts[contract_name]["versions"] = []

        self.contracts[contract_name]["versions"].append({
            "code": self.contracts[contract_name]["code"],
            "timestamp": time.time()
        })
    
        self.contracts[contract_name]["code"] = new_code
        self.contracts[contract_name]["state"] = existing_state

        self.save_contract_state()
        return {"message": f"Contract {contract_name} updated successfully."}, 200
        
    def transfer_contract_ownership(self, contract_name, new_owner, sender):
        """Allows the current owner to transfer contract ownership."""
        if contract_name not in self.contracts:
            return {"error": "Contract not found"}, 404

        if self.contracts[contract_name]["owner"] != sender:
            return {"error": "Unauthorized: Only the contract owner can transfer ownership"}, 403

        self.contracts[contract_name]["owner"] = new_owner
        self.save_contract_state()

        return {"message": f"Ownership of {contract_name} transferred to {new_owner}"}, 200
        
    def delete_contract(self, contract_name, sender):
        """Delete a contract, only if the sender is the owner."""
        if contract_name not in self.contracts:
            return {"error": "Contract not found"}, 404

        if self.contracts[contract_name]["owner"] != sender:
            return {"error": "Unauthorized: Only the contract owner can delete it"}, 403

        del self.contracts[contract_name]
        self.save_contract_state()
    
        return {"message": f"Contract {contract_name} deleted successfully."}, 200
            
ifchain = None

def get_ifchain_instance():
    port = int(os.getenv("FLASK_RUN_PORT", 5001))  # Get port from environment or default to 5001
    return IFChain(port=port)  # ✅ Pass the port

ifchain = get_ifchain_instance()

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

@app.route('/create_wallet', methods=['POST'])
def create_wallet():
    """Generates a new wallet and returns the private key, public key, and wallet address."""
    instance = get_ifchain_instance()  # Get the IFChain instance
    wallet = instance.generate_wallet()  # Generate the wallet
    return jsonify(wallet), 200  # Return wallet information as JSON
    
@app.route('/inflation_schedule', methods=['GET'])
def get_inflation_schedule():
    """Returns the inflation schedule."""
    return jsonify(ifchain.generate_inflation_schedule()), 200

@app.route('/apply_inflation', methods=['POST'])
def apply_inflation():
    """Applies inflation for the current year if not already applied."""
    success = ifchain.apply_inflation()
    if success:
        return jsonify({"message": "Inflation applied successfully"}), 200
    return jsonify({"error": "Inflation already applied or not available for this year"}), 400

@app.route('/add_new_transaction', methods=['POST'])
def add_new_transaction():
    """Adds a new transaction to the unconfirmed transaction pool."""

    tx_data = request.get_json()
    instance = get_ifchain_instance()
    
    print(f"Received transaction: {tx_data}")  # Debugging
    
    required_fields = ["sender", "receiver", "amount", "token"]
    if not all(field in tx_data for field in required_fields):
        print("Transaction failed: Missing required fields.")
        return jsonify({"error": "Missing required fields"}), 400

    sender = tx_data["sender"]
    receiver = tx_data["receiver"]
    amount = tx_data["amount"]
    token = tx_data["token"]
    
    gas_fee = amount * instance.gas_fee
    net_amount = amount - gas_fee

    sender_balance = instance.get_wallet_balance(sender).get("balance", {}).get(token, 0)
    
    print(f"Sender balance: {sender_balance} IFC | Required: {amount + gas_fee} IFC")

    if sender_balance < (amount + gas_fee):
        print("Transaction failed: Insufficient funds.")
        return jsonify({"error": "Insufficient balance"}), 400

    transaction = {
        "sender": sender,
        "receiver": receiver,
        "amount": amount,
        "token": token,
        "gas_fee": gas_fee,
        "net_amount": net_amount,
        "hash": hashlib.sha256(json.dumps(tx_data, sort_keys=True).encode()).hexdigest(),
        "timestamp": time.time(),
        "tx_type": "transfer",
        "block_confirmations": 0,
        "status": "pending",
        "signatures": []
    }

    instance.unconfirmed_transactions.append(transaction)

    # ✅ Save the updated unconfirmed transactions
    instance.save_pending_transactions()

    print(f"Transaction added successfully: {transaction}")

    return jsonify({"message": "Transaction added to the pool"}), 201

    
@app.route('/broadcast_transaction', methods=['POST'])
def broadcast_transaction():
    """Broadcasts a new transaction to all peers."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Invalid transaction data"}), 400

    transaction = {
        "sender": data["sender"],
        "receiver": data["receiver"],
        "amount": data["amount"],
        "token": data["token"],
        "gas_fee": 1.0,  # Adjust as needed
        "net_amount": data["amount"] - 1.0,  # Subtract gas fee
        "hash": hashlib.sha256(json.dumps(data).encode()).hexdigest(),
        "timestamp": time.time(),
        "tx_type": "transfer",
        "block_confirmations": 0,
        "status": "pending",
        "signatures": []
    }

    # Add to local node
    ifchain.unconfirmed_transactions.append(transaction)

    # Broadcast to peers
    for peer in ifchain.peers:
        try:
            response = requests.post(f"{peer}/receive_transaction", json=transaction)
            if response.status_code != 201:
                print(f"Failed to send transaction to {peer}")
        except requests.exceptions.RequestException:
            print(f"Error communicating with peer {peer}")

    return jsonify({"message": "Transaction broadcasted"}), 201
  
@app.route('/mine', methods=['GET'])
def mine():
    """Mine a block, rewarding the miner with gas fees."""
    miner_wallet = request.args.get('miner_wallet')

    if not miner_wallet:
        return jsonify({"error": "Miner wallet address required"}), 400

    result = ifchain.mine(miner_wallet)

    if not result:
        return jsonify({"error": "No transactions to mine"}), 400

    return jsonify({"message": result}), 200
    
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
    """Retrieve the total supply of IFC tokens."""
    return jsonify({"total_supply": ifchain.get_total_supply()}), 200
    
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


@app.route('/contract_code/<contract_name>', methods=['GET'])
def get_contract_code(contract_name):
    """Fetch the stored code of a specific smart contract."""
    if contract_name in ifchain.contracts:
        return jsonify({
            "contract_name": contract_name,
            "code": ifchain.contracts[contract_name]["code"]
        }), 200
    return jsonify({"error": "Contract not found"}), 404
    
@app.route('/execute_contract', methods=['POST'])
def execute_contract():
    """Execute a function from a deployed smart contract, applying gas fees and state updates."""
    data = request.get_json()

    # Check required fields
    required_fields = ["contract_name", "function", "params", "caller"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing contract execution details"}), 400

    contract_name = data["contract_name"]
    function_name = data["function"]
    params = data["params"]
    caller = data["caller"]

    if contract_name not in ifchain.contracts:
        return jsonify({"error": "Contract not found"}), 404

    contract_code = ifchain.contracts[contract_name]["code"]
    contract_state = ifchain.contracts[contract_name]["state"]

    # Ensure contract logs exist
    if "logs" not in ifchain.contracts[contract_name]:
        ifchain.contracts[contract_name]["logs"] = []

    # Load contract functions dynamically
    local_scope = {"state": contract_state}
    try:
        exec(contract_code, {}, local_scope)  # Execute contract code
    except Exception as e:
        return jsonify({"error": f"Failed to load contract code: {str(e)}"}), 400

    # Ensure the function exists
    if function_name not in local_scope or not callable(local_scope[function_name]):
        return jsonify({"error": f"Function '{function_name}' not found in contract"}), 400

    # Charge gas fee
    gas_fee = ifchain.GAS_FEE_PER_CONTRACT_EXECUTION
    caller_balance = ifchain.get_wallet_balance(caller).get("balance", {}).get("IFC", 0)

    if caller_balance < gas_fee:
        return jsonify({"error": "Insufficient balance for gas fee"}), 400

    # Deduct gas fee from caller's wallet
    ifchain.force_add_balance(caller, -gas_fee, "IFC")

    try:
        # Execute contract function
        result = local_scope[function_name](**params)

        # Ensure the contract state is updated
        ifchain.contracts[contract_name]["state"] = local_scope["state"]

        # Log execution details
        execution_log = {
            "timestamp": time.time(),
            "contract_name": contract_name,
            "function": function_name,
            "params": params,
            "result": result,
            "executed_by": caller,
            "gas_fee": gas_fee
        }
        ifchain.contracts[contract_name]["logs"].append(execution_log)

        # Save contract state after execution
        ifchain.save_contract_state()

        return jsonify({
            "message": f"Function '{function_name}' executed successfully.",
            "result": result,
            "gas_fee_deducted": gas_fee,
            "log_entry": execution_log
        }), 200

    except Exception as e:
        return jsonify({"error": f"Contract execution failed: {str(e)}"}), 400
 
@app.route('/update_contract', methods=['PUT'])
def update_contract():
    """Update a contract only if the request is from the owner and retains logs/state."""
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
    existing_logs = ifchain.contracts[contract_name].get("logs", [])
    
    if "versions" not in ifchain.contracts[contract_name]:
        ifchain.contracts[contract_name]["versions"] = []

    ifchain.contracts[contract_name]["versions"].append({
        "code": ifchain.contracts[contract_name]["code"],
        "timestamp": time.time()
    })
    
    ifchain.contracts[contract_name]["code"] = new_code
    ifchain.contracts[contract_name]["state"] = existing_state
    ifchain.contracts[contract_name]["logs"] = existing_logs  # 🔹 Preserve logs
    ifchain.save_contract_state()

    return jsonify({
        "message": f"Contract {contract_name} updated successfully.",
        "versions": len(ifchain.contracts[contract_name]["versions"])
    }), 200
   
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
    """Fetch execution logs of a specific smart contract, ensuring past features are retained."""
    
    if contract_name not in ifchain.contracts:
        return jsonify({"error": "Contract not found"}), 404
    
    contract_data = ifchain.contracts[contract_name]
    
    if "logs" not in contract_data or not contract_data["logs"]:
        return jsonify({
            "contract_name": contract_name,
            "logs": [],
            "message": "No logs found for this contract."
        }), 200
    
    return jsonify({
        "contract_name": contract_name,
        "logs": contract_data["logs"]
    }), 200
    
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
    
@app.route('/api/total-transactions', methods=['GET'])
def get_total_transactions():
    """Retrieve the total number of transactions in the blockchain."""
    total_transactions = sum(len(block.transactions) for block in ifchain.chain)

    return jsonify({"count": total_transactions}), 200
    
@app.route('/wallet_transactions/<wallet_address>', methods=['GET'])
def get_wallet_transactions(wallet_address):
    """Retrieve all transactions involving a specific wallet address with filtering options."""
    
    token_filter = request.args.get('token')
    transaction_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    transactions = []

    for block in ifchain.chain:
        try:
            # Ensure timestamp is always treated as a float
            block_time = datetime.utcfromtimestamp(float(block.timestamp)).strftime('%Y-%m-%d %H:%M:%S')
            block_timestamp = datetime.strptime(block_time, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue  # Skip invalid timestamps

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
    
@app.route('/get_wallet_balance', methods=['GET'])
def api_get_wallet_balance():
    wallet_address = request.args.get('wallet_address')

    if not wallet_address:
        return jsonify({"error": "Wallet address is required"}), 400

    try:
        balance = ifchain.get_wallet_balance(wallet_address)  # Calls the function you provided
        return jsonify(balance), 200
    except Exception as e:
        print(f"Error fetching wallet balance: {e}")  # Debugging logs
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

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
        try:
            # Convert timestamp to Unix format if stored as a string
            if isinstance(block.timestamp, str):
                block_timestamp = datetime.strptime(block.timestamp, '%Y-%m-%d %H:%M:%S').timestamp()
            else:
                block_timestamp = float(block.timestamp)  # Ensure float for Unix timestamp
        except ValueError:
            return jsonify({"error": "Invalid block timestamp format"}), 400

        block_time = datetime.utcfromtimestamp(block_timestamp).strftime('%Y-%m-%d %H:%M:%S')

        if block_number is not None and block.index != block_number:
            continue
        if start_date and end_date:
            try:
                start_timestamp = datetime.strptime(start_date, "%Y-%m-%d").timestamp()
                end_timestamp = datetime.strptime(end_date, "%Y-%m-%d").timestamp()
                if not (start_timestamp <= block_timestamp <= end_timestamp):
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
    
@app.route('/block/latest', methods=['GET'])
def get_latest_block():
    """
    Retrieve the latest block.
    """
    if len(ifchain.chain) == 0:
        return jsonify({"error": "No blocks available"}), 404

    latest_block = ifchain.chain[-1]  # Get the last block
    return jsonify(latest_block.to_dict()), 200
    
@app.route('/blockNumber', methods=['GET'])
def get_latest_block_number():
    """
    Retrieve the latest block number.
    """
    if not ifchain.chain:
        return jsonify({"error": "Blockchain is empty"}), 404

    latest_block = ifchain.chain[-1]  # Get the last block
    return jsonify({"blockNumber": latest_block.index}), 200
    
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
    """Returns all unconfirmed transactions."""
    
    instance = get_ifchain_instance()

    # ✅ Load pending transactions before returning
    instance.load_pending_transactions()

    print("DEBUG: Returning unconfirmed transactions:", instance.unconfirmed_transactions)

    return jsonify({
        "pending_transactions": instance.unconfirmed_transactions,
        "total_pending": len(instance.unconfirmed_transactions)
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
        "latest_block": latest_block,
        "chain_id": ifchain.chain_id  # Add Chain ID to the overview
    }), 200
   
@app.route('/block/<block_hash>', methods=['GET'])
def get_block_by_hash(block_hash):
    """Retrieve a block by its hash."""
    for block in ifchain.chain:
        if block.compute_hash() == block_hash:
            return jsonify(block.to_dict()), 200
    return jsonify({"error": "Block not found"}), 404
  
@app.route('/peers', methods=['GET'])
def get_peers():
    """Returns the list of registered peers."""
    return jsonify({"peers": list(ifchain.peers)}), 200
    
@app.route('/register_peer', methods=['POST'])
def register_peer():
    """Registers a new peer node, ensuring it does not register itself."""
    data = request.get_json()
    peer = data.get("peer")

    if not peer:
        return jsonify({"error": "Peer address required"}), 400

    # Get this node's own address
    self_address = f"http://127.0.0.1:{ifchain.port}"

    # Prevent self-registration
    if peer == self_address:
        return jsonify({"error": "Cannot add self as a peer"}), 400

    if peer not in ifchain.peers:
        ifchain.register_peer(peer)
        return jsonify({"message": f"Peer {peer} added successfully", "peers": list(ifchain.peers)}), 200

    return jsonify({"message": "Peer already exists", "peers": list(ifchain.peers)}), 200

@app.route('/receive_block', methods=['POST'])
def receive_block():
    """Receives and validates a new block from peers before adding it."""
    block_data = request.get_json()
    print(f"DEBUG: Received block from peer: {block_data}")  # 🔍 Debugging

    new_block = Block(**block_data)

    # Get the last block in the local chain
    last_block = ifchain.last_block()

    # Validate block index
    if new_block.index != last_block.index + 1:
        print(f"❌ Block rejected: Incorrect index. Expected {last_block.index + 1}, got {new_block.index}")
        return jsonify({"error": "Block rejected: Incorrect index"}), 400

    # Validate previous hash
    if new_block.previous_hash != last_block.hash:
        print(f"❌ Block rejected: Previous hash mismatch. Expected {last_block.hash}, got {new_block.previous_hash}")
        return jsonify({"error": "Block rejected: Previous hash mismatch"}), 400

    # ✅ Fix: Accept the PoH hash from the incoming block
    if hasattr(new_block, "poh_hash"):
        print(f"🔄 Updating PoH hash from peer: {new_block.poh_hash}")
        ifchain.poh.current_hash = new_block.poh_hash  # ✅ Accept PoH hash

    # If all checks pass, add the block
    if ifchain.add_block(new_block, new_block.hash):
        print(f"✅ Block {new_block.index} accepted and added to chain!")
        return jsonify({"message": "Block accepted"}), 200

    print("❌ Block rejected: Failed validation.")
    return jsonify({"error": "Block rejected"}), 400



@app.route('/receive_transaction', methods=['POST'])
def receive_transaction():
    """Receives a transaction from another node and prevents rebroadcast loops."""

    tx_data = request.get_json()
    print(f"Received transaction from peer: {tx_data}")

    # Add 'origin' field to prevent resending it back
    tx_data["origin"] = request.host_url.rstrip('/')

    required_fields = ["sender", "receiver", "amount", "token"]
    if not all(field in tx_data for field in required_fields):
        print("Transaction failed: Missing required fields.")
        return jsonify({"error": "Invalid transaction data"}), 400

    # Prevent duplicate transactions
    existing_hashes = {tx["hash"] for tx in ifchain.unconfirmed_transactions}
    if tx_data["hash"] in existing_hashes:
        print(f"Transaction already exists, skipping: {tx_data['hash']}")
        return jsonify({"message": "Transaction already exists"}), 200

    success = ifchain.add_new_transaction(tx_data)
    
    if success:
        print(f"Transaction accepted and added: {tx_data}")
        return jsonify({"message": "Transaction received and added"}), 201

    print(f"Transaction rejected: {tx_data}")
    return jsonify({"error": "Invalid transaction"}), 400

    
@app.route('/sync_chain', methods=['GET'])
def sync_chain():
    """API endpoint to synchronize blockchain with peers."""
    if ifchain.sync_chain():
        return jsonify({"message": "Blockchain synchronized successfully."}), 200
    return jsonify({"error": "No longer chain found or sync failed."}), 400
    
@app.route('/execute_contract_call', methods=['POST', 'GET'])
def execute_contract_call():
    """Execute a smart contract function without modifying state (read-only calls)."""

    if request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
        
        contract_name = data.get("contract_name")
        function_name = data.get("function_name")
        params = data.get("params", {})  # Get params or empty dict
    else:
        contract_name = request.args.get("contract_name")
        function_name = request.args.get("function_name")
        params = request.args.get("params", "{}")  # Default to empty JSON string
        
        try:
            params = json.loads(params)  # Convert JSON string to dict
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid params format"}), 400

    if not contract_name or not function_name:
        return jsonify({"error": "Missing contract_name or function_name"}), 400

    if contract_name not in ifchain.contracts:
        return jsonify({"error": "Contract not found"}), 404

    contract_data = ifchain.contracts[contract_name]
    contract_code = contract_data["code"]
    contract_state = contract_data["state"]
    
    local_scope = {"state": contract_state}
    exec(contract_code, {}, local_scope)

    if function_name not in local_scope or not callable(local_scope[function_name]):
        return jsonify({"error": f"Function '{function_name}' not found in contract '{contract_name}'"}), 404

    try:
       
        result = local_scope[function_name](**params)
        return jsonify({
            "contract": contract_name,
            "function": function_name,
            "result": result
        }), 200
    except TypeError as e:
        return jsonify({"error": f"Function call error: {str(e)}"}), 400
    
@app.route('/transfer_contract_ownership', methods=['POST'])
def api_transfer_contract_ownership():
    """API endpoint to transfer contract ownership."""
    data = request.get_json()

    if "contract_name" not in data or "new_owner" not in data or "sender" not in data:
        return jsonify({"error": "Missing contract name, new owner, or sender"}), 400

    result, status_code = ifchain.transfer_contract_ownership(data["contract_name"], data["new_owner"], data["sender"])
    return jsonify(result), status_code

@app.route('/delete_contract/<contract_name>', methods=['DELETE'])
def api_delete_contract(contract_name):
    """API endpoint to delete a contract (only owner can delete)."""
    sender = request.args.get("sender")

    if not sender:
        return jsonify({"error": "Sender address required"}), 400

    result, status_code = ifchain.delete_contract(contract_name, sender)
    return jsonify(result), status_code
    
@app.route('/force_add_balance', methods=['POST'])
def api_force_add_balance():
    """Manually adds balance to a wallet (used for testing and admin purposes)."""
    data = request.get_json()
    
    if "wallet_address" not in data or "token" not in data or "amount" not in data:
        return jsonify({"error": "Missing wallet_address, token, or amount"}), 400

    wallet_address = data["wallet_address"]
    token = data["token"]
    amount = data["amount"]

    instance = get_ifchain_instance()
    
    success = instance.force_add_balance(wallet_address, token, amount)
    
    if success:
        return jsonify({"message": f"{amount} {token} added to {wallet_address}"}), 200
    return jsonify({"error": "Failed to add balance"}), 400
    
@app.route('/gas_fee', methods=['GET'])
def get_gas_fee():
    instance = get_ifchain_instance()
    return jsonify({"gas_fee": instance.gas_fee}), 200
    
@app.route('/blockchain', methods=['GET'])
def get_blockchain():
    return get_chain()
    
@app.route('/save_blockchain', methods=['POST'])
def save_blockchain():
    global blockchain  # Ensure Flask recognizes the blockchain instance
    blockchain.save_blockchain_state()
    return jsonify({"message": "Blockchain state saved successfully"}), 200
    
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "✅ IFChain API is Live on DigitalOcean!"})

# ✅ Ensure this route exists
@app.route("/api/transaction-details", methods=["POST"])
def get_transactions():
    transactions = [
        {
            "hash": "0x144c9e104c3b14...",
            "blockNo": 2,
            "from": "0xf39Fd6e51aad88...",
            "to": "0x70997970C51812...",
            "value": "0.01",
            "token": "IF..."
        }
    ]
    return jsonify(transactions)
    
@app.route('/api/stats', methods=['POST'])
def get_stats():
    return jsonify({
        "totalSupply": "1,000,000 IFC",
        "totalTransactions": 5000,
        "totalBlocks": 100,
        "totalWallets": 5000,
        "avgBlockTime": "2.1s"
    })
    
@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "running", "network": "IFChain"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))  # Use Render's PORT env variable
    app.run(host="0.0.0.0", port=port)



