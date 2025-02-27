const express = require('express');
const cors = require('cors');  // ✅ Import CORS correctly
const { ethers } = require('ethers'); // Import ethers.js

console.log("✅ Running server.js from:", __dirname);

const app = express();
const port = 3000;

// ✅ Correct CORS Placement
const corsOptions = {
    origin: ["https://ifchain.io", "https://choy-ce.onrender.com"],
    methods: "GET,POST",
    allowedHeaders: ["Content-Type"]
};
app.use(cors(corsOptions));
// ✅ Middleware setup
app.use(express.json()); // Fixes request body parsing issue
app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*"); // Allow all or specify domains
    res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");
    next();
});


// ✅ Connect to IFChain Local Blockchain
const provider = new ethers.JsonRpcProvider("https://eth-sepolia.g.alchemy.com/v2/Q1B8NywX_0C-HDhGK9l1aF_jN_khHNlB");

// ✅ Fetch Wallet Balance (POST)
app.post('/api/balance', async (req, res) => {
    try {
        const { address } = req.body;

        // Validate Ethereum address
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
            return res.status(400).json({ error: "Missing parameters (privateKey, to, amount)" });
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

app.get('/api/transaction-details', (req, res) => {
    res.status(400).json({ error: "Use POST instead of GET" });
});

app.post('/api/transaction-details', async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();

        // Debugging Log
        console.log("Latest Block:", latestBlock);
        if (!latestBlock || latestBlock < 0) {
            throw new Error("Invalid block number fetched from provider.");
        }

        const transactions = [];

        for (let i = latestBlock; i > latestBlock - 10 && i >= 0; i--) {
            const block = await provider.getBlockWithTransactions(i); // ✅ Fixed

            if (!block || !block.transactions) continue;

            for (const tx of block.transactions) { // ✅ No need for separate getTransaction()
                transactions.push({
                    hash: tx.hash,
                    blockNo: tx.blockNumber,
                    from: tx.from,
                    to: tx.to,
                    value: ethers.formatEther(tx.value),
                    token: "IF..."
                });
            }
        }

        if (transactions.length === 0) {
            return res.status(404).json({ error: "No recent transactions found" });
        }

        res.json(transactions);
    } catch (error) {
        console.error("❌ Error:", error);
        res.status(500).json({ error: error.message });
    }
});



app.post('/api/transactions', async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const transactions = [];

        // ✅ Ensure we don't go below block 0
        const startBlock = Math.max(0, latestBlock - 30);

        for (let i = latestBlock; i > startBlock; i--) {
            const block = await provider.getBlock(i);
            if (!block) continue;  // ✅ Skip if block is null

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

app.post("/api/stats", async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const totalTransactions = latestBlock * 5; // Replace with real data
        const totalWallets = 5000; // Replace with actual count
        const avgBlockTime = "2.1s"; // Replace with actual avg block time

        res.json({
            totalSupply: "1,000,000 IFC",  // Replace with real supply
            totalTransactions,
            totalBlocks: latestBlock,
            totalWallets,
            avgBlockTime
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.get("/", (req, res) => {
    res.json({ message: "✅ IFChain API is Live on Localhost!" });
});

// ✅ Start Server with Improved Error Handling
app.listen(port, '0.0.0.0', () => {
    console.log(`🚀 Server is running on http://localhost:${port}`);
}).on('error', (err) => {
    console.error("❌ Server Error:", err.message);

    // Handle specific errors
    if (err.code === 'EADDRINUSE') {
        console.error(`❌ Port ${port} is already in use. Try using a different port.`);
    } else if (err.code === 'EACCES') {
        console.error(`❌ Permission denied. Try running the command with sudo.`);
    } else {
        console.error("❌ Unknown Server Error:", err);
    }
});
