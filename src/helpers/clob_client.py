import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

def create_clob_client() -> ClobClient:
    load_dotenv()

    host = "https://clob.polymarket.com"
    key = os.getenv('PK')  # Your exported private key from Polymarket

    # Get proxy wallet from environment variable
    polymarket_proxy_address = os.getenv('PROXY_WALLET')
    if not polymarket_proxy_address:
        raise ValueError("PROXY_WALLET not found in .env file")

    client = ClobClient(
        host=host,
        key=key,
        chain_id=POLYGON,
        signature_type=1,
        funder=polymarket_proxy_address
    )
    
    # Create or derive API credentials automatically
    client.set_api_creds(client.derive_api_key())
    
    return client