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

    spent_usdc = 0
    received_amount = 0
    destination = None

    logger.info(f"Processing transaction: {tx}")

    transfers = tx.get('tokenTransfers', [])
    if not transfers:
        logger.info("No token transfers found in this transaction")
        return None
    
    is_buy = False

    if isinstance(transfers, list):
        for transfer in transfers:
            token_amount = transfer.get('tokenAmount')
            if token_amount is not None and token_amount != 0:
                token_amount = float(token_amount) / (10 ** transfer.get('decimals', 0))

            mint_address = transfer.get('mint')

            if mint_address == APR_TOKEN_MINT:
                received_amount += token_amount
                destination = transfer.get('toUserAccount') or transfer.get('to') or transfer.get('destination')
                is_buy = True  # Mark this as a buy transaction
                logger.info(f"RAPR Token received: {received_amount}, Destination: {destination}")

            elif mint_address == USDC_TOKEN_MINT:
                spent_usdc = token_amount
                logger.info(f"USDC spent: {spent_usdc}")

    # If it's a buy, calculate the transaction value and proceed
    if is_buy and spent_usdc >= 150:
        max_emoji_count = 220
        dolphin_emoji_usdc = "🐬" * min(int(spent_usdc / 10), max_emoji_count)

        caption = (
            f"Retarded APR Buy with USDC!\n"
            f"{dolphin_emoji_usdc}\n"
            f"\n"
            f"🔀 Spent {spent_usdc:.2f} USDC\n"
            f"🔀 Received {received_amount:.2f} APR\n"
            f'👤 <a href="https://solscan.io/account/{destination}">Buyer</a> | <a href="https://solscan.io/tx/{signature}">Txn</a>\n'
            f"💲 RAPR Price: ${price:.4f}\n"
            f"💸 Market Cap: ${market_cap:,.0f}\n"
            f"\n"
            f'📈 <a href="https://dexscreener.com/solana/bcraylvgewjrdwvwj7ftpzy2vxk8gttb9t8w2mcw2bb9">Chart</a> ⏫ <a href="https://x.com/RetardedAPR">Twitter</a> ✳️ <a href="https://www.retardedapr.com/">Website</a>'
        )

        logger.info(f"Transfer caption created: {caption}")
        return caption
    else:
        logger.info("No relevant token transfer detected in this transaction or not a buy transaction.")
        return None

async def monitor_token():
    processed_signatures = set()
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
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="Patchfix Test Start")
        logger.info("Test message sent successfully")
    except Exception as e:
        logger.exception(f"Failed to send test message: {e}")

    await monitor_token()

if __name__ == '__main__':
    asyncio.run(main())
