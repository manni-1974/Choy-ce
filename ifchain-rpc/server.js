const express = require('express');
const cors = require('cors');
const axios = require('axios');
const { ethers } = require('ethers');

const app = express();
const serverPort = process.env.PORT || 10000;  // ✅ Matches Render's port

const dns = require('dns');

const discoveryHostname = process.env.RENDER_DISCOVERY_SERVICE || "ifc-blockchain.onrender.com"; // Default to blockchain URL

function fetchAndPrintIPs() {
  dns.lookup(discoveryHostname, { all: true, family: 4 }, (err, addresses) => {
    if (err) {
      console.error('Error resolving DNS:', err);
      return;
    }
    const ips = addresses.map(a => a.address);
    console.log(`✅ IP addresses for ${discoveryHostname}: ${ips.join(', ')}`);
  });
}

fetchAndPrintIPs();
// ✅ CORS Configuration (Update this when moving to production)
const corsOptions = {
    origin: "*", // ⚠️ Allow all for now, but restrict in production (e.g., `https://your-framer-site.com`)
    methods: ["GET", "POST", "PUT", "DELETE"], // ✅ Ensure all needed HTTP methods are allowed
    allowedHeaders: ["Content-Type", "Authorization"], // ✅ Allow essential headers
};

const blockchainUrl = process.env.BLOCKCHAIN_URL || "https://ifc-blockchain.onrender.com";

console.log("✅ providerUrl set to:", blockchainUrl);

app.use(cors());
app.use(express.json());

app.get('/api/health', async (req, res) => {
    try {
        console.log("🔄 Checking blockchain health:", blockchainUrl);
        const response = await axios.get(`${blockchainUrl}/blockchain_overview`, { timeout: 5000 });

        return res.json({
            status: "API is running",
            provider: blockchainUrl,
            blockchain_status: response.data
        });
    } catch (error) {
        console.error("🚨 Error connecting to blockchain:", error.message);
        return res.status(500).json({
            error: "Blockchain backend is unreachable",
            details: error.message
        });
    }
});

// ✅ Prevent Infinite Loops
process.on('SIGTERM', () => {
    console.log("🛑 Server shutting down...");
    process.exit(0);
});

app.get('/api/block/:block_identifier?', async (req, res) => {
    try {
        let blockIdentifier = req.params.block_identifier;

        // If no block identifier is provided, fetch the latest block
        if (!blockIdentifier) {
            const blockNumberResponse = await axios.get("http://127.0.0.1:5001/blockNumber");
            blockIdentifier = blockNumberResponse.data.blockNumber;
        }

        const response = await axios.get(`http://127.0.0.1:5001/block/${blockIdentifier}`);
        res.json(response.data);
    } catch (error) {
        console.error("Error fetching block details:", error.message);
        res.status(500).json({ error: "Failed to fetch block details" });
    }
});

// ✅ API to Fetch the Latest Block
app.get('/api/block/latest', async (req, res) => {
    try {
        // Fetch the latest block number first
        const blockNumberResponse = await axios.get("http://127.0.0.1:5001/blockNumber");
        const latestBlockNumber = blockNumberResponse.data.blockNumber;

        // Now fetch the latest block using the retrieved block number
        const latestBlockResponse = await axios.get(`http://127.0.0.1:5001/block/${latestBlockNumber}`);
        res.json(latestBlockResponse.data);
    } catch (error) {
        console.error("Error fetching latest block:", error.message);
        res.status(500).json({ error: "Failed to fetch latest block details" });
    }
});

// ** 🔹 Use Flask API Instead of ethers.JsonRpcProvider **
const FLASK_RPC_URL = process.env.IFCHAIN_RPC || "http://127.0.0.1:5001";

// ** 🛠 Block Number Endpoint **
app.get("/blockNumber", async (req, res) => {
    try {
        const response = await axios.get(`${FLASK_RPC_URL}/blockNumber`);
        res.json(response.data);  // ✅ Directly return the API response
    } catch (error) {
        console.error("Error fetching block number:", error.message);
        res.status(500).json({ error: error.message });
    }
});

console.log("Using RPC URL:", process.env.IFCHAIN_RPC || "http://127.0.0.1:5001");
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
        const { privateKey, to, receiver, amount, sender } = req.body;

        // Allow both "to" and "receiver" fields for flexibility
        const recipient = to || receiver;

        if (!recipient || !amount) {
            return res.status(400).json({ error: "Missing parameters (to or receiver, amount)" });
        }

        // Remove ethers.js validation since IFChain uses a custom address format
        // if (!ethers.isAddress(recipient)) {
        //     return res.status(400).json({ error: "Invalid recipient address" });
        // }

        if (privateKey) {
            const wallet = new ethers.Wallet(privateKey, provider);
            const amountInWei = ethers.parseEther(amount.toString());
            const tx = await wallet.sendTransaction({ to: recipient, value: amountInWei });
            await tx.wait();
            return res.json({ message: "Transaction successful", txHash: tx.hash });
        }

        // Simulate transaction if no private key is provided
        const transaction = {
            sender: sender || "unknown",
            receiver: recipient,
            amount,
            timestamp: Date.now(),
        };

        console.log("New transaction added:", transaction);

        return res.json({ success: true, message: "Transaction added for testing", transaction });
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

app.get('/api/transactions', async (req, res) => {
    try {
        // Fetch latest block transactions
        const overviewResponse = await axios.get(`${blockchainUrl}/blockchain_overview`);
        const latestBlockTransactions = overviewResponse.data.latest_block.transactions || [];

        // Fetch pending transactions separately
        const pendingResponse = await axios.get(`${blockchainUrl}/pending_transactions`);
        const pendingTransactions = pendingResponse.data.pending_transactions || [];

        // Ensure transactions are formatted properly
        const formattedTransactions = latestBlockTransactions.map(tx => ({
            date: new Date(tx.timestamp * 1000).toLocaleDateString(),
            sender: tx.sender,
            receiver: tx.receiver,
            amount: tx.amount,
            status: tx.status || "confirmed",
            token: tx.token || "IFC",
            hash: tx.hash
        }));

        const formattedPendingTransactions = pendingTransactions.map(tx => ({
            date: new Date(tx.timestamp * 1000).toLocaleDateString(),
            sender: tx.sender,
            receiver: tx.receiver,
            amount: tx.amount,
            status: "pending",
            token: tx.token || "IFC",
            hash: tx.hash || "N/A"
        }));

        const allTransactions = [...formattedTransactions, ...formattedPendingTransactions];

        // Remove duplicate transactions based on hash
        const uniqueTransactions = allTransactions.filter(
            (tx, index, self) => index === self.findIndex((t) => t.hash === tx.hash)
        );

        res.json({ transactions: uniqueTransactions });
    } catch (error) {
        console.error("Error fetching transactions:", error);
        res.status(500).json({ error: "Failed to fetch transactions", details: error.message });
    }
});

app.get('/api/contract/:contract_name', async (req, res) => {
    const response = await fetch(`http://localhost:5000/get_contract_code/${req.params.contract_name}`);
    const data = await response.json();
    res.json(data);
});

app.get('/api/peers', async (req, res) => {
    const response = await fetch('http://localhost:5000/get_peers');
    const data = await response.json();
    res.json(data);
});

app.post('/api/sync', async (req, res) => {
    const response = await fetch('http://localhost:5000/sync_chain', { method: 'POST' });
    const data = await response.json();
    res.json(data);
});

app.post('/api/mint', async (req, res) => {
    const { token, amount } = req.body;
    const response = await fetch('http://localhost:5000/mint_tokens', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, amount })
    });
    const data = await response.json();
    res.json(data);
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


