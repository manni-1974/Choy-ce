import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import HomePage from "./HomePage";
import WalletConnectPage from "./WalletConnectPage";  // Correct path if necessary
import { Buffer } from 'buffer';
global.Buffer = Buffer;

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/wallet-connect" element={<WalletConnectPage />} />
      </Routes>
    </Router>
  );
}

export default App;


