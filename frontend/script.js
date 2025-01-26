async function fetchBlockchain() {
    try {
        const response = await fetch('https://choy-ce.onrender.com/blockchain');
        const data = await response.json();
        const outputElement = document.getElementById('blockchain-output');
        outputElement.innerHTML = JSON.stringify(data, null, 2);
    } catch (error) {
        console.error('Error fetching blockchain data:', error);
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
        fetchBlockchain(); // Refresh the blockchain display
    } catch (error) {
        console.error('Error adding transaction:', error);
        alert('Failed to add transaction. Please try again.');
    }
}

window.onload = fetchBlockchain;