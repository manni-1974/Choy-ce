async function fetchBlockchain() {
    try {
        const response = await fetch('https://choy-ce.onrender.com/blockchain');
        const data = await response.json();
        const tableBody = document.getElementById('blockchain-output');
        tableBody.innerHTML = '';
        data.chain.forEach(block => {
            block.transactions.forEach(tx => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${block.hash}</td>
                    <td>${new Date(block.timestamp * 1000).toLocaleString()}</td>
                    <td>${block.poh}</td>
                    <td>${tx.sender}</td>
                    <td>${tx.receiver}</td>
                    <td>${tx.amount}</td>
                `;
                tableBody.appendChild(row);
            });
        });
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
        fetchBlockchain();
    } catch (error) {
        console.error('Error adding transaction:', error);
        alert('Failed to add transaction. Please try again.');
    }
}

function setupFilters() {
    document.querySelectorAll('th[data-filter]').forEach(header => {
        header.addEventListener('click', () => {
            const filterKey = header.getAttribute('data-filter');
            const rows = Array.from(document.querySelectorAll('#blockchain-output tr'));
            const sortedRows = rows.sort((a, b) => {
                const aText = a.querySelector(`td:nth-child(${header.cellIndex + 1})`).textContent;
                const bText = b.querySelector(`td:nth-child(${header.cellIndex + 1})`).textContent;
                return aText.localeCompare(bText);
            });
            const tableBody = document.getElementById('blockchain-output');
            tableBody.innerHTML = '';
            sortedRows.forEach(row => tableBody.appendChild(row));
        });
    });
}

window.onload = () => {
    document.getElementById('view-blockchain').addEventListener('click', fetchBlockchain);
    document.getElementById('add-transaction').addEventListener('click', addTransaction);
    setupFilters();
};







