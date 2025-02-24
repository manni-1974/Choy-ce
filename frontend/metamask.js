
// ✅ Function to Fetch Wallet Balance
async function getWalletBalance() {
    if (typeof window.ethereum === "undefined") {
        alert("MetaMask is not installed!");
        return;
    }

    try {
        console.log("Fetching wallet balance...");

        const provider = new ethers.providers.Web3Provider(window.ethereum);
        const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
        const walletAddress = accounts[0];

        const balance = await provider.getBalance(walletAddress);
        const balanceInEth = ethers.utils.formatEther(balance); // Convert from Wei to ETH

        console.log("Wallet Balance:", balanceInEth);
        document.getElementById("wallet-balance").innerText = `Balance: ${balanceInEth} ETH`;
    } catch (error) {
        console.error("Error fetching balance:", error);
    }
}

// ✅ Function to Send ETH Transaction
async function sendTransaction() {
    if (typeof window.ethereum === "undefined" || !window.ethereum.isMetaMask) {
        alert("Please install and enable MetaMask!");
        return;
    }

    try {
        console.log("Requesting MetaMask accounts...");
        const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
        const sender = accounts[0];

        console.log("Using sender address:", sender);

        const provider = new ethers.providers.Web3Provider(window.ethereum);
        const signer = provider.getSigner();

        // ✅ Get user-input ETH amount
        const ethAmount = document.getElementById("eth-amount").value;
        if (!ethAmount || parseFloat(ethAmount) <= 0) {
            alert("Please enter a valid ETH amount.");
            return;
        }

        const transaction = {
            to: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", // ✅ Correct recipient address
            value: ethers.utils.parseEther(ethAmount), // ✅ Convert ETH to Wei
            gasLimit: ethers.BigNumber.from("21000"), // ✅ Fixed Gas Limit
            gasPrice: await provider.getGasPrice(),
        };

        console.log("Sending transaction:", transaction);

        const txResponse = await signer.sendTransaction(transaction);
        console.log("Transaction Sent! Tx Hash:", txResponse.hash);
        alert("Transaction Sent! Tx Hash: " + txResponse.hash);

        // ✅ Wait for transaction confirmation
        await txResponse.wait();
        console.log("Transaction confirmed!");

        // ✅ Auto-update balance after transaction
        getWalletBalance();
    } catch (error) {
        console.error("Transaction Failed:", error);
        alert("Transaction Failed: " + error.message);
    }
}

// ✅ Automatically fetch balance on page load
window.onload = getWalletBalance;
