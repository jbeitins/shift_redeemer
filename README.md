# shift_redeemer
Lean and straigtforward Python script that fetches SHIFT codes for Borderlands games and automatically redeems them. Set up cron and forget about it.

Data can be sourced either from https://github.com/ugoogalizer/autoshift-codes or scraped directly from https://mentalmars.com/game-news/borderlands-4-shift-codes.

Dont forget to configure config path (for log, redeemed code history and cookies), platform and URLs to be checked.

SHIFT cookies are saved after first login. 

Redeemed codes are saved so they are not retried again.

Platform can be either 'steam' or 'epic'.

No expiry checks built in. If using https://github.com/ugoogalizer/autoshift-codes as a source, on first run script will attempt to redeem bunch of old, expired codes. Enable DRY_RUN to build up cache without attempting to redeem them.

## Credits
Login and redeeming mechanics borrowed from https://github.com/denverquane/slickshift/

Scraping from https://github.com/ugoogalizer/autoshift-scraper/
