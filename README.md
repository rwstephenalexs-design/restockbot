# Pokemon restock bot (retail only)

Watches product pages at Target, Best Buy, Amazon, Pokemon Center, and Walmart.
The moment something is in stock at or under the MSRP you set, it:

1. pushes an urgent notification to your phone,
2. clicks **Add to Cart** in your own logged-in Chrome on your PC,
3. pushes again with a link to the cart.

You then open the retailer's app on your phone, where the item is already in
the cart because carts sync to your account, and you pay with Apple Pay or
Google Pay. Any captcha on the pay step is yours to tap. That is the design:
the bot does the time-critical carting, you do the ten-second checkout.

It does **not** solve captchas, use proxies, store your card, or buy more than
one of anything. The hard caps live in `config.json`.

## One-time setup (about 15 minutes)

### 1. Install

```powershell
cd $HOME\Documents\pokemon-restock-bot
python -m pip install -r requirements.txt
python -m playwright install chromium
```

(If you have Google Chrome installed the bot uses it. The `playwright install`
line is the fallback if it doesn't find Chrome.)

### 2. Phone pushes (ntfy, free, no account)

1. Install the **ntfy** app from the App Store or Play Store.
2. In the app, tap **+** and subscribe to a topic. Pick a long random name
   nobody would guess, like `pika-7f3k9q2-xr`. That name is the only secret.
3. Put the same name in `config.json` under `ntfy.topic`.
4. In the phone's settings, allow ntfy to send notifications and turn off
   battery optimization for it so pushes arrive instantly.

### 3. Config

```powershell
copy config.example.json config.json
```

Edit `config.json`:

- `products`: one entry per product page you want. Use the exact product URL
  you'd open in a browser. Set `max_price` to MSRP (or a little over for tax
  math, the price checked is the listed price).
- `ntfy.topic`: your topic name from step 2.
- `discord_webhook`: optional second channel.

### 4. Log in once

```powershell
python -m bot login
```

A Chrome window opens with a tab per retailer. Sign in to each, and make sure
each account has your shipping address and a saved card. Press Enter in the
terminal when done. Logins live in `chrome-profile/` and survive restarts.

Also sign in to each retailer's **phone app** and enable Apple Pay or Google
Pay there. This is the step that actually wins drops.

### 5. Test

```powershell
python -m bot test-notify
python -m bot probe "https://www.target.com/p/your-product-url"
```

`probe` opens the page, prints what the bot detected (in stock, price, seller)
and saves a screenshot to `probes/`. Do this for every product once.
Retailer page layouts change, so if a probe says out-of-stock for something
you can see is in stock, the selectors in `bot/retailers/<site>.py` need a
small update.

## Running

```powershell
python -m bot run --dry-run     # notifies only, never clicks
python -m bot run               # the real thing
```

Leave the terminal and the Chrome window open. Don't use that Chrome window
for anything else while it runs. Press Ctrl+C to stop.

After a successful cart the product is marked done in `state.json` and will
not be carted again. To watch it again later:

```powershell
python -m bot reset "https://www.target.com/p/your-product-url"
```

## What the notifications mean

| Title | What to do |
|---|---|
| IN STOCK: ... | Open the retailer app now. Carting is in progress. |
| CARTED: ... | Item is in your cart. Check out from the app. |
| Cart failed: ... | Auto-cart didn't work. Tap the link and add it by hand. |
| ...: bot check | Site showed a verification page on the PC. Solve it there or via Chrome Remote Desktop. |
| Waiting room: ... | Pokemon Center queue is up. Bot holds its place. |

## Keeping it polite and low-risk

- Default poll is a random 30 to 60 seconds per product, with jitter between
  pages. Going much faster raises the odds a retailer blocks or flags you.
- It runs from your home IP in a real browser. Don't move it to a cloud box;
  retailers block datacenter IPs at the first click.
- `max_buys_per_product` and `daily_buy_limit` are there on purpose.
- Automated add-to-cart is against these stores' terms of use. Orders do get
  cancelled occasionally. One item, one account, your own browser is the
  lowest-risk way to do this, but it isn't zero.

## Files

```
bot/__main__.py          CLI: login, test-notify, probe, run, reset
bot/monitor.py           poll loop, guards, notifications
bot/browser.py           persistent Chrome profile via Playwright
bot/notify.py            ntfy + Discord
bot/state.py             what's been carted, cooldowns
bot/retailers/*.py       per-site stock, price, seller, add-to-cart logic
config.json              your watchlist (gitignored)
```
