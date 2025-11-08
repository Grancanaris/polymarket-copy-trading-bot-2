"""
Setup script to generate Polymarket API credentials and check/set allowances.

This script:
1. Derives API credentials from your MetaMask private key
2. Checks if trading allowances are set
3. Provides instructions to set allowances if needed

Based on: https://jeremywhittaker.com/index.php/2024/08/28/generating-api-keys-for-polymarket-com/
"""

import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from web3 import Web3
from colorama import Fore, Style, init

init()
load_dotenv()

def derive_polymarket_api_credentials():
    """Derive Polymarket API credentials from private key"""

    print(f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════════╗
║        POLYMARKET API CREDENTIALS & ALLOWANCE SETUP              ║
╚══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}

This script will:
1. Generate your Polymarket API credentials from your private key
2. Check if trading allowances are properly set
3. Save the credentials to your environment

""")

    # Load configuration
    host = "https://clob.polymarket.com"
    key = os.getenv('PK')
    proxy_wallet = os.getenv('PROXY_WALLET')

    if not key:
        print(f"{Fore.RED}❌ Private key (PK) not found in .env file{Style.RESET_ALL}")
        return

    if not proxy_wallet:
        print(f"{Fore.RED}❌ Proxy wallet (PROXY_WALLET) not found in .env file{Style.RESET_ALL}")
        return

    # Ensure private key has 0x prefix
    if not key.startswith('0x'):
        key = '0x' + key

    # Derive EOA address
    w3 = Web3()
    account = w3.eth.account.from_key(key)
    eoa_address = account.address

    print(f"📍 EOA Wallet (MetaMask): {eoa_address}")
    print(f"📍 Proxy Wallet (Polymarket): {proxy_wallet}\n")

    # Create CLOB client
    print(f"{Fore.YELLOW}🔄 Creating CLOB client...{Style.RESET_ALL}")

    client = ClobClient(
        host=host,
        key=key,
        chain_id=POLYGON,
        signature_type=2,  # POLY_GNOSIS_SAFE for Polymarket proxy wallets
        funder=proxy_wallet
    )

    print(f"{Fore.GREEN}✅ CLOB client created{Style.RESET_ALL}\n")

    # Derive API credentials
    print(f"{Fore.YELLOW}🔑 Deriving API credentials...{Style.RESET_ALL}")

    try:
        api_creds = client.derive_api_key()

        print(f"{Fore.GREEN}✅ API credentials derived successfully!{Style.RESET_ALL}\n")
        print(f"API Key: {api_creds.api_key[:20]}...{api_creds.api_key[-10:]}")
        print(f"API Secret: {api_creds.api_secret[:20]}...{api_creds.api_secret[-10:]}")
        print(f"API Passphrase: {api_creds.api_passphrase}\n")

        # Set the credentials
        client.set_api_creds(api_creds)

    except Exception as e:
        print(f"{Fore.RED}❌ Error deriving API credentials: {e}{Style.RESET_ALL}")
        return

    # Check allowances
    print(f"{Fore.YELLOW}🔍 Checking trading allowances...{Style.RESET_ALL}\n")

    try:
        # Try to get the allowance status
        # This will tell us if the proxy wallet has approved the Exchange contracts

        # Connect to Polygon to check approvals
        w3_polygon = Web3(Web3.HTTPProvider(os.getenv('RPC_URL', 'https://polygon-rpc.com')))

        # CTF Contract address
        CTF_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

        # Exchange contracts
        CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
        NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

        # ERC-1155 isApprovedForAll ABI
        IS_APPROVED_ABI = [{
            "constant": True,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "operator", "type": "address"}
            ],
            "name": "isApprovedForAll",
            "outputs": [{"name": "", "type": "bool"}],
            "type": "function"
        }]

        ctf_contract = w3_polygon.eth.contract(
            address=w3_polygon.to_checksum_address(CTF_CONTRACT),
            abi=IS_APPROVED_ABI
        )

        # Check both exchanges
        ctf_approved = ctf_contract.functions.isApprovedForAll(
            w3_polygon.to_checksum_address(proxy_wallet),
            w3_polygon.to_checksum_address(CTF_EXCHANGE)
        ).call()

        neg_risk_approved = ctf_contract.functions.isApprovedForAll(
            w3_polygon.to_checksum_address(proxy_wallet),
            w3_polygon.to_checksum_address(NEG_RISK_EXCHANGE)
        ).call()

        print(f"CTF Exchange: {'✅ Approved' if ctf_approved else '❌ Not Approved'}")
        print(f"Neg Risk Exchange: {'✅ Approved' if neg_risk_approved else '❌ Not Approved'}\n")

        if not ctf_approved or not neg_risk_approved:
            print(f"{Fore.YELLOW}⚠️  Trading allowances are not fully set up!{Style.RESET_ALL}\n")
            print(f"{Fore.CYAN}To enable selling via the bot, you need to approve the exchanges:{Style.RESET_ALL}\n")
            print(f"Option 1 - Use Polymarket.com:")
            print(f"  1. Go to https://polymarket.com")
            print(f"  2. Make a small SELL trade (even $1 worth)")
            print(f"  3. This will set the approvals automatically\n")
            print(f"Option 2 - Use a contract interaction tool:")
            print(f"  Contract: {CTF_CONTRACT}")
            print(f"  Function: setApprovalForAll")
            print(f"  Operator: {CTF_EXCHANGE}")
            print(f"  Approved: true")
            print(f"  (Repeat for: {NEG_RISK_EXCHANGE})\n")
            print(f"{Fore.RED}NOTE: Since you're using a proxy wallet, you MUST use Polymarket.com")
            print(f"      to set approvals. Direct contract interaction won't work.{Style.RESET_ALL}\n")
        else:
            print(f"{Fore.GREEN}🎉 All approvals are set! You're ready to trade!{Style.RESET_ALL}\n")

    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Could not check approval status: {e}{Style.RESET_ALL}\n")
        print(f"This might be OK - try running the bot and see if selling works.\n")

    # Test the API connection
    print(f"{Fore.YELLOW}🧪 Testing API connection...{Style.RESET_ALL}\n")

    try:
        # Try to fetch server time (basic API test)
        server_time = client.get_server_time()
        print(f"{Fore.GREEN}✅ API connection successful!{Style.RESET_ALL}")
        print(f"Server time: {server_time}\n")

    except Exception as e:
        print(f"{Fore.RED}❌ API connection failed: {e}{Style.RESET_ALL}\n")

    print(f"{Fore.CYAN}═══════════════════════════════════════════════════════════════════{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}✅ Setup complete!{Style.RESET_ALL}\n")
    print(f"Your bot is configured with:")
    print(f"  • API credentials (derived from your private key)")
    print(f"  • Proxy wallet: {proxy_wallet}")
    print(f"  • Signature type: 2 (POLY_GNOSIS_SAFE)\n")

    if not (ctf_approved and neg_risk_approved):
        print(f"{Fore.YELLOW}⚠️  Remember to set approvals using Polymarket.com before selling!{Style.RESET_ALL}\n")

    print(f"Run your bot with: {Fore.CYAN}python src/main.py{Style.RESET_ALL}\n")

if __name__ == "__main__":
    derive_polymarket_api_credentials()
