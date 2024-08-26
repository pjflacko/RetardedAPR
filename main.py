import asyncio
import httpx
import logging
from telegram import Bot
from telegram.constants import ParseMode

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual bot token and chat ID
TELEGRAM_BOT_TOKEN = '7518581649:AAHxo3YOE4JOpLmFpTG_iPRDEFSUMsFOUlg'
TELEGRAM_CHAT_ID = '-4571973740'

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

# Set to track processed signatures
processed_signatures = set()

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
    timestamp = tx.get('timestamp')

    spent_usdc = None
    received_amount = 0
    destination = None

    logger.info(f"Processing transaction: {tx}")

    # Handle token transfers
    transfers = tx.get('tokenTransfers', [])
    if not transfers:
        logger.info("No token transfers found in this transaction")
        return None

    for transfer in transfers:
        token_amount = transfer.get('tokenAmount')
        if token_amount:
            token_amount = float(token_amount) / (10 ** transfer.get('decimals', 0))  # Handle decimals properly
            logger.info(f"Decoded token amount: {token_amount} {transfer.get('mint')}")

        mint_address = transfer.get('mint')
        logger.info(f"Token Transfer - Mint: {mint_address}, Amount: {token_amount}")

        if mint_address == USDC_TOKEN_MINT:
            spent_usdc = token_amount
            received_amount = spent_usdc / price
            logger.info(f"USDC spent: {spent_usdc}")

    if received_amount == 0:
        logger.warning("No relevant APR token received.")
        return None

    # Calculate the transaction value in USD
    total_transaction_value = spent_usdc if spent_usdc is not None else 0

    # Check if the total transaction value is at least $150
    if total_transaction_value < 150:
        logger.info(f"Transaction value is less than $150, skipping message. Value: ${total_transaction_value:.2f}")
        return None

    if spent_usdc is not None or received_amount is not None:
        max_emoji_count = 220
        dolphin_emoji_usdc = "🐬" * min(int(spent_usdc / 10), max_emoji_count) if spent_usdc is not None else ""
        dolphin_emoji = dolphin_emoji_usdc

        if spent_usdc is not None:
            caption = (
                f"Retarded APR Buy!\n"
                f"{dolphin_emoji}\n"
                f"\n"
                f"🔀 Spent {spent_usdc:.2f} USDC\n"
                f"🔀 Received {received_amount if received_amount is not None else 'Unknown Amount':.2f} APR\n"
                f'👤 <a href="https://solscan.io/account/{destination}">Buyer</a> | <a href="https://solscan.io/tx/{signature}">Txn</a>\n'
                f"💲 RAPR Price: ${price:.4f}\n"
                f"💸 Market Cap: ${market_cap:,.0f}\n"
                f"\n"
                f'📈 <a href="https://dexscreener.com/solana/bcraylvgewjrdwvwj7ftpzy2vxk8gttb9t8w2mcw2bb9">Chart</a> ⏫ <a href="https://x.com/RetardedAPR">Twitter</a> ✳️ <a href="https://www.retardedapr.com/">Website</a>'
            )
        else:
            caption = None  # No relevant pool transaction

        if caption:
            logger.info(f"Transfer caption created: {caption}")
            return caption

    logger.info("No relevant token transfer detected in this transaction")
    return None

async def monitor_token():
    global processed_signatures  # Ensure we reference the correct processed_signatures set
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

                logger.info(f"Received response: {transactions}")

                if isinstance(transactions, dict):
                    transactions_list = transactions.get('transactions', [])
                else:
                    transactions_list = transactions

                if not transactions_list:
                    logger.info("No transactions found")

                for tx in transactions_list:
                    signature = tx.get('signature')

                    if signature is None:
                        logger.warning(f"Transaction does not have a signature: {tx}")
                        continue

                    # Check if the signature has already been processed
                    if signature in processed_signatures:
                        logger.debug(f"Transaction {signature} has already been processed. Skipping.")
                        continue

                    caption = process_transaction(tx, price, market_cap)
                    if caption:
                        logger.info(f"Sending photo with caption to Telegram")
                        try:
                            await bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=PHOTO_URL, caption=caption, parse_mode=ParseMode.HTML)
                            logger.info("Photo with caption sent successfully")
                        except Exception as e:
                            logger.error(f"Failed to send Telegram message: {e}")
                            logger.error(f"Caption content: {caption}")  # Log the caption content

                    # Add the signature to the set of processed signatures
                    processed_signatures.add(signature)
                    logger.debug(f"Added transaction {signature} to processed_signatures set.")

                # Keep only the last 100 processed signatures to save memory
                if len(processed_signatures) > 100:
                    processed_signatures = set(list(processed_signatures)[-100:])

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
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="Start")
        logger.info("Test message sent successfully")
    except Exception as e:
        logger.exception(f"Failed to send test message: {e}")

    await monitor_token()

if __name__ == '__main__':
    asyncio.run(main())
