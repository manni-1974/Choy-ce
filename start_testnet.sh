#!/bin/bash

# Configuration
CHAIN_ID="ifchain-testnet"
NODE_COUNT=3
DATA_DIR="./testnet"

# Ensure testnet directory exists
mkdir -p $DATA_DIR
cd $DATA_DIR

# Initialize the blockchain using your Python script
echo "Initializing IFChain Testnet..."
python3 ../blockchain_app.py --init --chain-id $CHAIN_ID

# Create validator keys (modify based on your implementation)
for i in $(seq 1 $NODE_COUNT)
do
  echo "Setting up Validator $i..."
  python3 ../blockchain_app.py --create-validator --name validator$i
  python3 ../blockchain_app.py --add-genesis-account validator$i 1000000ifc
done

# Generate genesis transactions
python3 ../blockchain_app.py --gentx validator1 500000ifc
python3 ../blockchain_app.py --collect-gentxs

# Start the testnet
echo "Starting IFChain Testnet..."
python3 ../blockchain_app.py --start
