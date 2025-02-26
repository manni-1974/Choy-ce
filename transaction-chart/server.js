const express = require('express');
const cors = require('cors');
const { ethers } = require('ethers');  // Import ethers.js

const app = express();
const port = 3000;

// ✅ Middleware setup
app.use(express.json()); // Fixes request body parsing issue
app.use(cors()); // Allows all origins

// ✅ Connect to IFChain Local Blockchain
const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");

// ✅ Fetch Wallet Balance (Now Uses POST)
app.post('/api/balance', async (req, res) => {
    try {
        const { address } = req.body; // Expect address in the request body

        // Validate Ethereum address
        if (!ethers.isAddress(address)) {
            return res.status(400).json({ error: "Invalid Ethereum address" });
        }

        const balance = await provider.getBalance(address);
        res.json({ balance: ethers.formatEther(balance) });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ Send Transactions (POST)
app.post('/api/send', async (req, res) => {
    try {
        const { privateKey, to, amount } = req.body; // Expect sender private key, recipient, and amount

        if (!privateKey || !to || !amount) {
            return res.status(400).json({ error: "Missing parameters (privateKey, to, amount)" });
        }
        if (!ethers.isAddress(to)) {
            return res.status(400).json({ error: "Invalid recipient address" });
        }

        // Connect wallet with private key
        const wallet = new ethers.Wallet(privateKey, provider);

        // Convert amount to Wei
        const amountInWei = ethers.parseEther(amount.toString());

        // Create and send transaction
        const tx = await wallet.sendTransaction({
            to,
            value: amountInWei
        });

        // Wait for confirmation
        await tx.wait();

        res.json({ message: "Transaction successful", txHash: tx.hash });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ Fetch Real Blockchain Transactions (POST)
app.post('/api/transaction-details', async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const transactions = [];

        for (let i = latestBlock; i > latestBlock - 10; i--) {
            const block = await provider.getBlockWithTransactions(i);
            block.transactions.forEach((tx) => {
                transactions.push({
                    hash: tx.hash,
                    blockNo: tx.blockNumber,
                    from: tx.from,
                    to: tx.to,
                    value: ethers.formatEther(tx.value),
                    token: "IF..."
                });
            });
        }
        res.json(transactions);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ API to Fetch Chart Data (POST)
app.post('/api/transactions', async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const transactions = [];

        for (let i = latestBlock; i > latestBlock - 30; i--) {
            const block = await provider.getBlock(i);
            transactions.push({
                date: new Date(block.timestamp * 1000).toLocaleDateString(),
                count: block.transactions.length
            });
        }
        res.json(transactions);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ Start server
app.listen(port, () => {
    console.log(`🚀 Server is running on http://localhost:${port}`);
});
