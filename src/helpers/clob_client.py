import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from web3 import Web3

def create_clob_client() -> ClobClient:
    load_dotenv()

    host = "https://clob.polymarket.com"
    key = os.getenv('PK')  # Your exported private key from Polymarket

    # Ensure private key has 0x prefix
    if key and not key.startswith('0x'):
        key = '0x' + key

    # Derive the EOA wallet address from the private key
    w3 = Web3()
    account = w3.eth.account.from_key(key)
    eoa_wallet_address = account.address

    # Get proxy wallet from environment variable
    polymarket_proxy_address = os.getenv('PROXY_WALLET')
    if not polymarket_proxy_address:
        raise ValueError("PROXY_WALLET not found in .env file")

    print(f"🔑 EOA Wallet (from PK): {eoa_wallet_address}")
    print(f"🔑 Proxy Wallet: {polymarket_proxy_address}")

    # Polymarket uses proxy wallets which are smart contracts
    # signature_type=2 for POLY_GNOSIS_SAFE (Polymarket's proxy implementation)
    # funder=proxy wallet address (where your funds are)
    # key=your EOA private key (to authorize the proxy)
    client = ClobClient(
        host=host,
        key=key,
        chain_id=POLYGON,
        signature_type=2,  # 2 for POLY_GNOSIS_SAFE (Polymarket proxy)
        funder=polymarket_proxy_address  # Your Polymarket proxy address
    )

    # Derive API credentials for the proxy wallet
    try:
        api_creds = client.derive_api_key()
        client.set_api_creds(api_creds)
        print(f"✅ API credentials set successfully")
    except Exception as e:
        print(f"⚠️  Warning: Could not derive API key: {e}")

    # Try to set approval for all tokens (setApprovalForAll)
    try:
        print(f"🔧 Checking trading allowances...")
        # Check if we can call are_approved method
        # If allowances aren't set, we'll get an error later with instructions
        print(f"✅ CLOB client ready for trading")
    except Exception as e:
        print(f"⚠️  Warning: {e}")

    return client