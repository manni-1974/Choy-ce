const express = require('express');
const cors = require('cors');
const { ethers } = require('ethers');

const app = express();
const port = 3000;

// ✅ CORS Setup
const corsOptions = {
    origin: ["https://ifchain.io", "https://choy-ce.onrender.com"],
    methods: "GET,POST",
    allowedHeaders: ["Content-Type"]
};
app.use(cors(corsOptions));
app.use(express.json());

// ✅ IFChain Blockchain Connection (Update to Alchemy or other RPC)
const provider = new ethers.JsonRpcProvider("https://eth-sepolia.g.alchemy.com/v2/Q1B8NywX_0C-HDhGK9l1aF_jN_khHNlB"); // Change this if using Alchemy

// ✅ Fetch Wallet Balance (POST)
app.post('/api/balance', async (req, res) => {
    try {
        const { address } = req.body;

        if (!address || !ethers.isAddress(address)) {
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
        const { privateKey, to, amount } = req.body;

        if (!privateKey || !to || !amount) {
            return res.status(400).json({ error: "Missing parameters" });
        }
        if (!ethers.isAddress(to)) {
            return res.status(400).json({ error: "Invalid recipient address" });
        }

        const wallet = new ethers.Wallet(privateKey, provider);
        const amountInWei = ethers.parseEther(amount.toString());

        const tx = await wallet.sendTransaction({ to, value: amountInWei });
        await tx.wait();

        res.json({ message: "Transaction successful", txHash: tx.hash });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ Fetch Recent Transactions
app.post('/api/transaction-details', async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const transactions = [];

        for (let i = latestBlock; i > latestBlock - 10 && i >= 0; i--) {
            const block = await provider.getBlock(i);
            if (!block || !block.transactions) continue;

            for (const txHash of block.transactions) {
                const tx = await provider.getTransaction(txHash);  // ✅ Fetch full transaction
                if (!tx) continue;

                transactions.push({
                    hash: tx.hash,
                    blockNo: tx.blockNumber,
                    from: tx.from,
                    to: tx.to,
                    value: tx.value ? ethers.formatEther(tx.value) : "0",  // ✅ Ensure valid value
                    token: "IF..."
                });
            }
        }

        res.json(transactions);
    } catch (error) {
        console.error("❌ Error fetching transactions:", error);
        res.status(500).json({ error: error.message });
    }
});

// ✅ Fetch Blockchain Stats
app.post("/api/stats", async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const totalTransactions = latestBlock * 5; // Example calculation
        const totalWallets = 5000;
        const avgBlockTime = "2.1s";

        const stats = {
            totalSupply: "1,000,000 IFC",
            totalTransactions,
            totalBlocks: latestBlock,
            totalWallets,
            avgBlockTime
        };

        res.json(stats);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ Health Check API
app.get("/", (req, res) => {
    res.json({ message: "✅ IFChain API is Live on Render!" });
});

// ✅ Start Server
app.listen(port, '0.0.0.0', () => {
    console.log(`🚀 Server is running on http://localhost:${port}`);
});
