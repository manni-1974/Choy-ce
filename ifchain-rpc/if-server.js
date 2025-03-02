const express = require('express');
const cors = require('cors');
const { ethers } = require('ethers');
require('dotenv').config(); // ✅ Load environment variables

const app = express();
const serverPort = process.env.PORT || 3000;

// ✅ Unified CORS Setup (No Duplicates)
app.use(cors({
    origin: ["https://ifchain.io", "https://choy-ce.onrender.com"],
    methods: "GET, POST",
    allowedHeaders: ["Content-Type"]
}));

app.use(express.json()); // ✅ Parses incoming JSON requests

// ✅ Connect to IFChain RPC
const IFCHAIN_RPC = process.env.IFCHAIN_RPC || "https://rpc.ifchain.com";
const provider = new ethers.JsonRpcProvider(IFCHAIN_RPC);

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
            return res.status(400).json({ error: "Missing parameters (privateKey, to, amount)" });
        }
        if (!ethers.isAddress(to)) {
            return res.status(400).json({ error: "Invalid recipient address" });
        }

        const wallet = new ethers.Wallet(privateKey, provider);
        const tx = await wallet.sendTransaction({ to, value: ethers.parseEther(amount.toString()) });
        await tx.wait();
        res.json({ message: "Transaction successful", txHash: tx.hash });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ Transaction Details
app.post('/api/transaction-details', async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const transactions = [];
        for (let i = latestBlock; i > latestBlock - 10 && i >= 0; i--) {
            const block = await provider.getBlockWithTransactions(i);
            if (!block || !block.transactions) continue;
            for (const tx of block.transactions) {
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
        res.json(transactions.length ? transactions : { error: "No recent transactions found" });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ✅ IFChain JSON-RPC Endpoint
app.post("/", async (req, res) => {
    try {
        const { method, params, id } = req.body;
        if (!method) return res.status(400).json({ error: "Missing method in JSON-RPC request" });

        console.log(`📡 RPC Request Received: ${method}`);

        let result;
        switch (method) {
            case "eth_chainId":
                result = "0x270F"; // IFChain Chain ID (9999 in HEX)
                break;
            case "eth_blockNumber":
                result = ethers.toBeHex(await provider.getBlockNumber());
                break;
            case "eth_getBalance":
                if (!params || params.length === 0) return res.status(400).json({ error: "Missing address" });
                result = ethers.toBeHex(await provider.getBalance(params[0]));
                break;
            case "net_version":
                result = "9999"; // IFChain Network ID
                break;
            case "eth_gasPrice":
                result = ethers.toBeHex(await provider.getGasPrice());
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

// ✅ Default Route
app.get("/", (req, res) => {
    res.send("🚀 IFChain API is Running! Use /api/* endpoints.");
});

// ✅ Start Server
app.listen(serverPort, () => {
    console.log(`🚀 Server is running on port ${serverPort}`);
}).on('error', (err) => {
    console.error("❌ Server Error:", err.message);
    if (err.code === 'EADDRINUSE') {
        console.error(`❌ Port ${serverPort} is already in use.`);
    } else if (err.code === 'EACCES') {
        console.error(`❌ Permission denied.`);
    } else {
        console.error("❌ Unknown Server Error:", err);
    }
});
