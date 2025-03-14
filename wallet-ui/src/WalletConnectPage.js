import React, { useState, useEffect } from "react"
import WalletConnect from "@walletconnect/client"
import QRCodeModal from "@walletconnect/qrcode-modal"

export default function WalletConnectPage() {
    const [account, setAccount] = useState(null)
    const [connector, setConnector] = useState(null)

    useEffect(() => {
        // Automatically connect if the wallet is already connected
        if (connector && connector.connected) {
            const { accounts } = connector
            setAccount(accounts[0])
        }
    }, [connector])

    // Initialize WalletConnect
    const connectWallet = async () => {
        const wc = new WalletConnect({
            bridge: "https://bridge.walletconnect.org",
            qrcodeModal: QRCodeModal,
        })

        if (!wc.connected) {
            await wc.createSession()
        }

        wc.on("connect", (error, payload) => {
            if (error) {
                console.error(error)
            }
            const { accounts } = payload.params[0]
            setAccount(accounts[0]) // Set the account address
            setConnector(wc) // Store the WalletConnect instance
        })
    }

    // Disconnect wallet
    const disconnectWallet = async () => {
        if (connector) {
            await connector.killSession()
            setAccount(null)
        }
    }

    return (
        <div>
            <h1>Connect Your Wallet</h1>
            {account ? (
                <>
                    <p>Connected Account: {account}</p>
                    <button onClick={disconnectWallet}>Disconnect</button>
                </>
            ) : (
                <div>
                    <button onClick={connectWallet}>Connect Wallet</button>
                    <p>Scan the QR code with your wallet</p>
                </div>
            )}
        </div>
    )
}
