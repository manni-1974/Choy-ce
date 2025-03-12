// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract IFToken {
    string public name = "IFChain";  
    string public symbol = "IF...";  
    uint8 public decimals = 18;
    uint256 public totalSupply;
    uint256 public constant MAX_SUPPLY = 1_000_000_000 * (10 ** 18); // 1B IF...
    
    address public admin;
    address public constant BURN_ADDRESS = 0x000000000000000000000000000000000000dEaD; // 🔥 Burn address

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Mint(address indexed to, uint256 value);
    event GasFeePaid(address indexed sender, uint256 amount);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can perform this action");
        _;
    }
    
    constructor() {
        admin = msg.sender;
        totalSupply = 1_000_000_000 * (10 ** 18); // Initial supply (1B IF...)
        balanceOf[admin] = totalSupply;
        emit Transfer(address(0), admin, totalSupply);
    }

    // ✅ Transfer IF... tokens with gas fee deducted
    function transfer(address to, uint256 value) external returns (bool) {
        require(balanceOf[msg.sender] >= value, "Insufficient balance");

        uint256 gasFee = 10 * (10 ** decimals); // 🔥 Gas fee in IF...
        require(balanceOf[msg.sender] >= value + gasFee, "Not enough IF... for gas fee");

        balanceOf[msg.sender] -= (value + gasFee);
        balanceOf[to] += value;

        // 🔥 Send gas fee to burn address
        balanceOf[BURN_ADDRESS] += gasFee;
        emit GasFeePaid(msg.sender, gasFee);
        emit Transfer(msg.sender, to, value);
        return true;
    }

    // ✅ Approve an allowance for another address
    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    // ✅ Transfer from an approved allowance
    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        require(balanceOf[from] >= value, "Insufficient balance");
        require(allowance[from][msg.sender] >= value, "Allowance exceeded");

        uint256 gasFee = 10 * (10 ** decimals); // 🔥 Gas fee in IF...
        require(balanceOf[from] >= value + gasFee, "Not enough IF... for gas fee");

        balanceOf[from] -= (value + gasFee);
        balanceOf[to] += value;
        allowance[from][msg.sender] -= value;

        // 🔥 Send gas fee to burn address
        balanceOf[BURN_ADDRESS] += gasFee;
        emit GasFeePaid(from, gasFee);
        emit Transfer(from, to, value);
        return true;
    }

    // ✅ Mint new IF... tokens (Admin Only)
    function mint(address to, uint256 value) external onlyAdmin {
        require(totalSupply + value <= MAX_SUPPLY, "Max supply exceeded");
        totalSupply += value;
        balanceOf[to] += value;
        emit Mint(to, value);
        emit Transfer(address(0), to, value);
    }
}
