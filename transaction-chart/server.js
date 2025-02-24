const express = require('express');
const { faker } = require('@faker-js/faker');
const cors = require('cors');
const { ethers } = require('ethers');  // Import ethers.js

const app = express();
const port = 3000;

// ✅ Middleware setup
app.use(express.json()); // Fixes request body parsing issue
app.use(cors()); // Allows all origins

// ✅ Connect to local Ganache blockchain
const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");

// ✅ Function to fetch wallet balance
async function getWalletBalance(address) {
    try {
        // Validate Ethereum address (disable ENS lookup)
        if (!ethers.isAddress(address)) {
            throw new Error("Invalid Ethereum address");
        }

        const balance = await provider.getBalance(address);
        return { balance: ethers.formatEther(balance) };
    } catch (error) {
        return { error: error.message };
    }
}

// ✅ API endpoint to fetch wallet balance
app.get('/api/balance/:address', async (req, res) => {
    const result = await getWalletBalance(req.params.address);
    res.json(result);
});

// ✅ New API endpoint to send ETH transactions
app.post('/api/send', async (req, res) => {
    try {
        const { privateKey, to, amount } = req.body; // Get input data

        // Validate input
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

// ✅ Function to generate fake transactions for the chart (date and count)
const generateChartData = () => {
    const transactions = [];
    const currentDate = new Date();

    for (let i = 29; i >= 0; i--) {
        const date = new Date(currentDate);
        date.setDate(date.getDate() - i);

        // Generate fake transaction data for the chart
        const transactionCount = faker.number.int({ min: 10, max: 100 });

        transactions.push({
            date: date.toLocaleDateString(),  // MM/DD/YYYY
            count: transactionCount
        });
    }

    return transactions;
};

// ✅ API endpoint to get transaction data for the chart
app.get('/api/transactions', (req, res) => {
    const transactions = generateChartData();
    res.json(transactions);
});

// ✅ Function to generate fake transactions for the table (hash, blockNo, from, to, etc.)
const generateTransactionDetails = () => {
    const transactions = [];

    for (let i = 0; i < 10; i++) {
        transactions.push({
            hash: faker.string.hexadecimal({ length: 18 }),  // Fake hash (hexadecimal string)
            blockNo: faker.number.int({ min: 100, max: 200 }),  // Fake block number
            from: faker.finance.ethereumAddress(),  // Fake 'from' address
            to: faker.finance.ethereumAddress(),  // Fake 'to' address
            tax: `${faker.number.int({ min: 1, max: 5 })}%`,  // Fake tax percentage (1-5%)
            value: `$${faker.commerce.price({ min: 500, max: 5000 })}`,  // Fake value (amount in dollars)
            token: faker.helpers.arrayElement(['ETH', 'BTC', 'USDT', 'SOL'])  // Random token type
        });
    }

    return transactions;
};

// ✅ API endpoint to get transaction details for the table
app.get('/api/transaction-details', (req, res) => {
    const transactions = generateTransactionDetails();
    res.json(transactions);
});

// ✅ Start server
app.listen(port, () => {
    console.log(`Server is running on http://localhost:${port}`);
});
