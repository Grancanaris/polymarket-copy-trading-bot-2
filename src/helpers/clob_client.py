import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

def create_clob_client() -> ClobClient:
    load_dotenv()

    host = "https://clob.polymarket.com"
    key = os.getenv('PK')  # Your exported private key from Polymarket

    # Ensure private key has 0x prefix
    if key and not key.startswith('0x'):
        key = '0x' + key

    # Get proxy wallet from environment variable
    polymarket_proxy_address = os.getenv('PROXY_WALLET')
    if not polymarket_proxy_address:
        raise ValueError("PROXY_WALLET not found in .env file")

    # Use signature_type=0 for standard EOA wallets (MetaMask, etc)
    client = ClobClient(
        host=host,
        key=key,
        chain_id=POLYGON,
        signature_type=0,  # 0 for EOA, 1 for Gnosis Safe
        funder=polymarket_proxy_address
    )
    
    # Create or derive API credentials automatically
    client.set_api_creds(client.derive_api_key())
    
    return client