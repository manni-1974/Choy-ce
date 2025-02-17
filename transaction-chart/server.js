const express = require('express');
const { faker } = require('@faker-js/faker');
const cors = require('cors');
const app = express();
const port = 3000;

// Use CORS middleware
app.use(cors()); // Allow requests from all origins

// Function to generate fake transactions for the chart (date and count)
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

// Function to generate fake transactions for the table (hash, blockNo, from, to, etc.)
const generateTransactionDetails = () => {
    const transactions = [];

    for (let i = 0; i < 10; i++) {
        transactions.push({
            hash: faker.datatype.hexadecimal({ length: 18 }),  // Fake hash (hexadecimal string)
            blockNo: faker.number.int({ min: 100, max: 200 }),  // Fake block number
            from: faker.finance.ethereumAddress(),  // Fake 'from' address
            to: faker.finance.ethereumAddress(),  // Fake 'to' address
            tax: `${faker.number.int({ min: 1, max: 5 })}%`,  // Fake tax percentage (1-5%)
            value: `$${faker.commerce.price(500, 5000)}`,  // Fake value (amount in dollars)
            token: faker.helpers.randomize(['ETH', 'BTC', 'USDT', 'SOL'])  // Random token type
        });
    }

    return transactions;
};

// API endpoint to get transaction data for the chart
app.get('/api/transactions', (req, res) => {
    const transactions = generateChartData();
    res.json(transactions);  // Return the fake transactions for the chart
});

// API endpoint to get transaction details for the table
app.get('/api/transaction-details', (req, res) => {
    const transactions = generateTransactionDetails();
    res.json(transactions);  // Return the fake transactions for the table
});

app.listen(port, () => {
    console.log(`Server is running on http://localhost:${port}`);
});
