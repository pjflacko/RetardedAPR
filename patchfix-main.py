import asyncio
import httpx
import logging
from telegram import Bot
from telegram.constants import ParseMode

# Variables
pools = ["BcRAYLvgeWjrDwVWj7Ftpzy2vxK8GTTB9t8w2mcw2bB9"] # Additional Pools # "835MjqJNZm8rNDvuV87By7W1ynK1PSSZek3HEVD4jrqA","GQAC4vKAjSri8cUp7LATTVQvFCsvDKZyCiE5Su5gsCBe","44LTQiyX1Bc8RAtVT4jKMMhi6F6zFhh83d9jrieBRVpp","4xRwoJRMHCYDPLWRsLgwYgefPaGs9c3TetsgQSTezXsj"
show_buy_amt = 50

# Emoji Variables
max_emoji_count = 220
dollars_per_emoji = 10
emoji = "🐬"

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual bot token and chat ID
TELEGRAM_BOT_TOKEN = '7518581649:AAHxo3YOE4JOpLmFpTG_iPRDEFSUMsFOUlg'
TELEGRAM_CHAT_ID = '-4571973740' # '-1002248631555'

# Initialize the Telegram bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Helius API settings
HELIUS_API_URL = "https://api.helius.xyz/v0/addresses/{wallet_address}/transactions?api-key={api_key}"
API_KEY = '3f688505-35a6-4e9e-a0c3-564462b847b0'
WALLET_ADDRESS = 'RAPRz9fd87y9qcBGj1VVqUbbUM6DaBggSDA58zc3N2b'
API_URL = HELIUS_API_URL.format(wallet_address=WALLET_ADDRESS, api_key=API_KEY)

# Token Mint Addresses
APR_TOKEN_MINT = 'RAPRz9fd87y9qcBGj1VVqUbbUM6DaBggSDA58zc3N2b'
USDC_TOKEN_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'

# URL or local path of the image to display
PHOTO_URL = 'https://ibb.co/bs4m9qV'

DEX_SCREENER_API_URL = "https://api.dexscreener.com/latest/dex/pairs/solana/BcRAYLvgeWjrDwVWj7Ftpzy2vxK8GTTB9t8w2mcw2bB9"

signature_list = []

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)


async def get_token_data():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(DEX_SCREENER_API_URL)
            response.raise_for_status()
            data = response.json()

            # Extract relevant data
            price = data['pair']['priceUsd']
            market_cap = data['pair']['fdv']  # Fully diluted valuation as a proxy for market cap

            return float(price), float(market_cap)

        except Exception as e:
            logger.error(f"Failed to fetch token data: {e}")
            return None, None

def process_transaction(tx, price, market_cap):
    signature = tx.get('signature')

    is_buy = False
    spent_usdc = 0
    received_amount = 0
    destination = None

    logger.info('Processing transaction: {tx}')

    transfers = tx.get('tokenTransfers', [])
    if not transfers:
        logger.info("No token transfers found in this transaction")
        return None
    
    logger.info("Processing transfer.")

    # Extract token balance changes for the specific mint address
    target_mint = "RAPRz9fd87y9qcBGj1VVqUbbUM6DaBggSDA58zc3N2b"
    balance_changes = []

    # Iterate over the account data to find token balance changes
    for account in tx.get('accountData', []):
        for token_change in account.get('tokenBalanceChanges', []):
            if token_change.get('mint') == target_mint:
                balance_changes.append({
                    'userAccount': token_change.get('userAccount'),
                    'tokenAccount': token_change.get('tokenAccount'),
                    'rawTokenAmount': token_change.get('rawTokenAmount'),
                    'mint': token_change.get('mint')
                })

    # Log the token balance changes if userAccount is in pools
    for change in balance_changes:
        user_account = change['userAccount']
        raw_token_amount = change['rawTokenAmount']['tokenAmount']
        decimals = change['rawTokenAmount']['decimals']
        
        if user_account in pools:
            if float(raw_token_amount) < 0:
                logger.info(f"User Account: {change['userAccount']}")
                logger.info(f"Token Account: {change['tokenAccount']}")
                logger.info(f"Token Amount: {change['rawTokenAmount']['tokenAmount']}")
                logger.info(f"Decimals: {change['rawTokenAmount']['decimals']}")
                logger.info(f"Mint: {change['mint']}")
                is_buy = True
                received_amount = abs(float(raw_token_amount)) / (10 ** decimals)
                spent_usdc = received_amount*price
                logger.info("-" * 40)
            else:
                is_buy = False
                logger.info('TX not a buy.')
        else:
            logger.info("TX not from pool.")
            is_buy = False

    if is_buy and spent_usdc >= show_buy_amt:

        if signature in signature_list:
            logger.info("Duplicate Siganture Found - Skip")
            return None
        else:

            if len(signature_list) > 100:
               signature_list.pop(0)
            
            signature_list.append(signature)        
            
            emoji_usdc = emoji * min(int(spent_usdc / dollars_per_emoji), max_emoji_count)

            caption = (
                f"Retarded APR Buy with USDC!\n"
                f"{emoji_usdc}\n"
                f"\n"
                f"🔀 Spent {spent_usdc:.2f} USDC\n"
                f"🔀 Received {received_amount:.2f} APR\n"
                f'👤 <a href="https://solscan.io/account/{destination}">Buyer</a> | <a href="https://solscan.io/tx/{signature}">Txn</a>\n'
                f"💲 RAPR Price: ${price:.2f}\n"
                f"💸 Market Cap: ${market_cap:,.0f}\n"
                f"\n"
                f'📈 <a href="https://dexscreener.com/solana/bcraylvgewjrdwvwj7ftpzy2vxk8gttb9t8w2mcw2bb9">Chart</a> ⏫ <a href="https://x.com/RetardedAPR">Twitter</a> ✳️ <a href="https://www.retardedapr.com/">Website</a>'
            )

            logger.info(f"Transfer caption created: {caption}")
            return caption
    else:
        return None

async def monitor_token():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                price, market_cap = await get_token_data()

                if price is None or market_cap is None:
                    logger.error("Token data is unavailable, skipping transaction monitoring.")
                    await asyncio.sleep(60)
                    continue

                response = await client.get(API_URL)
                response.raise_for_status()
                transactions = response.json()

                # logger.info(f"Received response: {transactions}")

                if isinstance(transactions, dict):
                    transactions_list = transactions.get('transactions', [])
                else:
                    transactions_list = transactions

                if not transactions_list:
                    logger.info("No transactions found")
                    await asyncio.sleep(10)
                    continue

                for tx in transactions_list:
                    caption = process_transaction(tx, price, market_cap)
                    if caption:
                        logger.info(f"Sending photo with caption to Telegram")
                        try:
                            await bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=PHOTO_URL, caption=caption, parse_mode=ParseMode.HTML)
                            logger.info("Photo with caption sent successfully")
                        except Exception as e:
                            logger.error(f"Failed to send Telegram message: {e}")
                            logger.error(f"Caption content: {caption}")  # Log the caption content

                await asyncio.sleep(10)

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e}")
                logger.error(f"Error response: {e.response.text}")
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                await asyncio.sleep(60)

async def main():
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="Starting RAPR Buy Bot!")
        logger.info("Test message sent successfully")
    except Exception as e:
        logger.exception(f"Failed to send test message: {e}")

    await monitor_token()

if __name__ == '__main__':
    asyncio.run(main())
