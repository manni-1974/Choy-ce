const express = require('express');
const cors = require('cors');  // ✅ Import CORS correctly
const { ethers } = require('ethers'); // Import ethers.js

const app = express();
const serverPort = process.env.PORT || 3000;

require('dotenv').config();

const corsOptions = {
    origin: ["https://ifchain.io", "https://choy-ce.onrender.com"],
    methods: "GET, POST",
    allowedHeaders: ["Content-Type"]
};
app.use(cors(corsOptions));

app.use(express.json());
// ✅ Correct CORS Placement
const corsOptions = {
    origin: ["https://ifchain.io", "https://choy-ce.onrender.com"],
    methods: "GET,POST",
    allowedHeaders: ["Content-Type"]
};
app.use(cors(corsOptions));
// ✅ Middleware setup
app.use(express.json({ limit: "10mb" }));  // ✅ Increase request body size limit
app.use(express.urlencoded({ extended: true, limit: "10mb" })); // ✅ Handle URL-encoded data
app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*"); // Allow all or specify domains
    res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");
    next();
});


// ✅ Connect to IFChain Local Blockchain
const IFCHAIN_RPC = process.env.IFCHAIN_RPC || "https://rpc.ifchain.com";
const provider = new ethers.JsonRpcProvider(IFCHAIN_RPC);

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
    res.send("🚀 IFChain API is Running! Use /api/* endpoints.");
});

// ✅ JSON-RPC Endpoint for MetaMask & Wallets
app.post("/", async (req, res) => {
    try {
        const { method, params, id } = req.body;

        if (!method) {
            return res.status(400).json({ error: "Missing method in JSON-RPC request" });
        }

        console.log(`📡 RPC Request Received: ${method}`);

        let result;
        switch (method) {
            case "eth_chainId":
                result = "0x270F"; // ✅ IFChain Chain ID (9999 in HEX)
                break;
            case "eth_blockNumber":
                result = await provider.getBlockNumber();
                result = ethers.utils.hexValue(result);
                break;
            case "eth_getBalance":
                if (!params || params.length === 0) return res.status(400).json({ error: "Missing address" });
                result = await provider.getBalance(params[0]);
                result = ethers.utils.hexValue(result);
                break;
            case "net_version":
                result = "9999"; // ✅ IFChain Network ID
                break;
            case "eth_gasPrice":
                result = ethers.utils.hexValue(await provider.getGasPrice());
                break;
            default:
                return res.status(400).json({ error: `Method ${method} not supported for IFChain` });
        }

        res.json({ jsonrpc: "2.0", id, result });
    } catch (error) {
        console.error("❌ RPC Error:", error);
        res.status(500).json({ error: error.message });
    }
});
app.listen(serverPort, () => {
    console.log(`🚀 Server is running on port ${serverPort}`);
}).on('error', (err) => {
    console.error("❌ Server Error:", err.message);

    // Handle specific errors
    if (err.code === 'EADDRINUSE') {
        console.error(`❌ Port ${serverPort} is already in use. Try using a different port.`);
    } else if (err.code === 'EACCES') {
        console.error(`❌ Permission denied. Try running the command with sudo.`);
    } else {
        console.error("❌ Unknown Server Error:", err);
    }
});


