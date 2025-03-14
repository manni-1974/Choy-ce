import React, { useState } from "react";
import WalletConnect from "@walletconnect/client";
import QRCodeModal from "@walletconnect/qrcode-modal";  // Import QRCodeModal

const WalletConnectPage = () => {
  const [connected, setConnected] = useState(false);
  const [address, setAddress] = useState(null);

  const connectWallet = async () => {
    const walletConnector = new WalletConnect({
      bridge: "https://bridge.walletconnect.org", // Your bridge URL
      qrcodeModal: QRCodeModal,  // Ensure this is passed
    });

    if (!walletConnector.connected) {
      await walletConnector.createSession();
    }

    walletConnector.on("connect", (error, payload) => {
      if (error) throw error;
      const { accounts } = payload.params[0];
      setAddress(accounts[0]);
      setConnected(true);
    });
  };

  return (
    <div>
      <h1>WalletConnect Page</h1>
      {!connected ? (
        <div>
          <button onClick={connectWallet}>Connect Wallet</button>
          <p>Scan the QR code with your wallet</p>
        </div>
      ) : (
        <p>Connected to Wallet: {address}</p>
      )}
    </div>
  );
};

export default WalletConnectPage;
