async function fetchBlockchain() {
    try {
        const response = await fetch('/blockchain');
        const data = await response.json();
        displayBlockchain(data.chain);
    } catch (error) {
        console.error('Error fetching blockchain data:', error);
    }
}

function displayBlockchain(chain) {
    const outputElement = document.getElementById('blockchain-output');
    outputElement.innerHTML = chain.map(block => `
        <div class="block">
            <div>Time: ${new Date(block.timestamp * 1000).toLocaleString()}</div>
            <div>Action: ${block.poh}</div>
            <div>From: ${block.transactions.map(tx => tx.sender).join(', ')}</div>
            <div>To: ${block.transactions.map(tx => tx.receiver).join(', ')}</div>
            <div>Amount: ${block.transactions.map(tx => tx.amount).join(', ')}</div>
        </div>
    `).join('');
}

document.getElementById('view-blockchain').addEventListener('click', fetchBlockchain);

async function addTransaction() {
    const sender = prompt("Enter the sender's name:");
    const receiver = prompt("Enter the receiver's name:");
    const amount = parseFloat(prompt("Enter the transaction amount:"));

    if (!sender || !receiver || isNaN(amount)) {
        alert('Invalid transaction details. Please try again.');
        return;
    }

    try {
        const response = await fetch('/add_transaction', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sender, receiver, amount })
        });
        const result = await response.json();
        alert(result.message);
        fetchBlockchain();
    } catch (error) {
        console.error('Error adding transaction:', error);
        alert('Failed to add transaction. Please try again.');
    }
}

document.getElementById('add-transaction').addEventListener('click', addTransaction);
