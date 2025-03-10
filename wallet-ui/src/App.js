import React, { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [balance, setBalance] = useState(null);
  const walletAddress = "wallet1"; // Change this to test different wallets

  useEffect(() => {
    fetch(`http://138.197.3.201:3000/api/wallet/balance?address=${walletAddress}`)
      .then((response) => response.json())
      .then((data) => setBalance(data.balance?.IFC || 0))
      .catch((error) => console.error("Error fetching balance:", error));
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>IFChain Wallet</h1>
        <p>Wallet Address: {walletAddress}</p>
        <p>Balance: {balance} IFC</p>
      </header>
    </div>
  );
}

export default App;
