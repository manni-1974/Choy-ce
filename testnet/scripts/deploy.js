const hre = require("hardhat");

async function main() {
    const IFToken = await hre.ethers.getContractFactory("IFToken");
    const ifToken = await IFToken.deploy();

    console.log(`Deploying IF...`);
    await ifToken.waitForDeployment(); // ✅ Fix: Replace .deployed() with .waitForDeployment()

    console.log(`✅ IF... deployed to: ${await ifToken.getAddress()}`); // ✅ Fix: Use getAddress()
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});


