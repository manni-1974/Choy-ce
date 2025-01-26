async function fetchBlockchain() {
    try {
        const response = await fetch('https://choy-ce.onrender.com/blockchain');
        const data = await response.json();
        const outputElement = document.getElementById('blockchain-output');
        outputElement.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Signature</th>
                        <th>Time</th>
                        <th>Action</th>
                        <th>From</th>
                        <th>To</th>
                        <th>Amount</th>
                        <th>Token</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.chain.map(block => block.transactions.map(tx => `
                        <tr>
                            <td>${block.hash}</td>
                            <td>${new Date(block.timestamp * 1000).toLocaleString()}</td>
                            <td>${tx.action || 'Transfer'}</td>
                            <td>${tx.sender}</td>
                            <td>${tx.receiver}</td>
                            <td>${tx.amount}</td>
                            <td>${tx.token || 'N/A'}</td>
                        </tr>
                    `).join('')).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error fetching blockchain data:', error);
        alert('Failed to fetch blockchain data. Please try again.');
    }
}

async function addTransaction() {
    const sender = prompt("Enter the sender's name:");
    const receiver = prompt("Enter the receiver's name:");
    const amount = parseFloat(prompt("Enter the transaction amount:"));

    if (!sender || !receiver || isNaN(amount)) {
        alert('Invalid transaction details. Please try again.');
        return;
    }

    try {
        const response = await fetch('https://choy-ce.onrender.com/add_transaction', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ sender, receiver, amount }),
        });

        const result = await response.json();
        alert(result.message);
        fetchBlockchain();
    } catch (error) {
        console.error('Error adding transaction:', error);
        alert('Failed to add transaction. Please try again.');
    }
}

document.getElementById('view-blockchain').addEventListener('click', fetchBlockchain);
document.getElementById('add-transaction').addEventListener('click', addTransaction);
