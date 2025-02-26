const express = require('express');
const cors = require('cors');
const { ethers } = require('ethers');
const { google } = require("googleapis");
const keys = require("./serviceAccount.json");  // ✅ Load Google Sheets credentials

const app = express();
const port = 3000;

// ✅ Google Sheets Auth Setup
const auth = new google.auth.GoogleAuth({
    credentials: keys,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});
const sheetsClient = google.sheets({ version: "v4", auth });

const SHEET_NAME = "IFChainData";  // ✅ Ensure this is correct
const SPREADSHEET_ID = "19VzYmyPLvSWQ4VrXM7uIWQCgJxUPj-ug2fRRxCoOW-A";  // ✅ Ensure correct Google Sheet ID

// ✅ CORS Setup
const corsOptions = {
    origin: ["https://ifchain.io", "https://choy-ce.onrender.com"],
    methods: "GET,POST",
    allowedHeaders: ["Content-Type"]
};
app.use(cors(corsOptions));
app.use(express.json());

// ✅ IFChain Local Blockchain Connection
const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");

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
        const block = await provider.getBlock(latestBlock, true);
        const totalTransactions = latestBlock * 5;  // Example calculation
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

// ✅ Save Blockchain Data to Google Sheets
async function writeToSheet(data) {
    try {
        const values = [[
            data.totalSupply,
            data.totalTransactions,
            data.totalBlocks,
            data.totalWallets,
            data.avgBlockTime,
            data.transactions,
            data.time,
            data.block,
            data.from,
            data.to,
            data.value,
            data.token
        ]];

        await sheetsClient.spreadsheets.values.append({
            spreadsheetId: SPREADSHEET_ID,
            range: `'Sheet1'!A:L`,
            valueInputOption: "RAW",
            insertDataOption: "INSERT_ROWS",
            resource: { values },
        });

        console.log("✅ Data successfully written to Google Sheets!");
    } catch (error) {
        console.error("❌ Google Sheets Update Failed:", error);
        throw error;
    }
}

// ✅ API to Update Google Sheets with Blockchain Data
app.post("/api/update-sheet", async (req, res) => {
    try {
        const latestBlock = await provider.getBlockNumber();
        const block = await provider.getBlock(latestBlock);  // ✅ Fetch block
        let recentTx = null;

        if (block && block.transactions.length > 0) {
            recentTx = await provider.getTransaction(block.transactions[0]); // ✅ Fetch first transaction
        }

        const blockchainStats = {
            totalSupply: "1,000,000 IFC",
            totalTransactions: latestBlock * 5, // Example calculation
            totalBlocks: latestBlock,
            totalWallets: 5000, // Example value
            avgBlockTime: "2.1s",
            transactions: recentTx ? recentTx.hash : "N/A",
            time: new Date().toISOString(),
            block: latestBlock,
            from: recentTx ? recentTx.from : "N/A",
            to: recentTx ? recentTx.to : "N/A",
            value: recentTx ? ethers.formatEther(recentTx.value) : "N/A",
            token: "IFC"
        };

        await writeToSheet(blockchainStats);
        res.json({ message: "✅ Data added to Google Sheets!" });
    } catch (error) {
        console.error("❌ Error updating Google Sheets:", error);
        res.status(500).json({ error: error.message });
    }
});

// ✅ Start Server
app.listen(port, '0.0.0.0', () => {
    console.log(`🚀 Server is running on http://localhost:${port}`);
});
