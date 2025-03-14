import React from "react";
import { useNavigate } from "react-router-dom";

const HomePage = () => {
  const navigate = useNavigate();

  const handleConnectWallet = () => {
    navigate("/wallet-connect"); // This will redirect to WalletConnectPage
  };

  return (
    <div>
      <h1>Welcome to IFChain</h1>
      <button onClick={handleConnectWallet}>Connect Wallet</button>
    </div>
  );
};

export default HomePage;


