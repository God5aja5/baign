import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

TELEGRAM_BOT_TOKEN = '7750500532:AAEQLLyqugCHdBodLJ6dsZ-SIx4EovZWrOE'
TELEGRAM_CHAT_ID = '7749807563'

def send_to_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    response = requests.post(url, data=payload)
    return response

def check_braintree_usage(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False
        soup = BeautifulSoup(response.content, 'html.parser')
        braintree_indicators = [
            r'braintreegateway\.com', r'braintreepayments\.com', r'client-analytics\.braintreegateway\.com',
            r'payments\.braintree-api\.com', r'https://js\.braintreegateway\.com/web/dropin/',
            r'https://js\.braintreegateway\.com/web/3\.\d+/js/client\.min\.js', r'braintree-web\.js',
            r'braintree-hosted-fields', r'braintree-data\.js', r'window\.braintree',
            r'braintree\.client\.create', r'braintree\.hostedFields\.create', r'braintree\.dataCollector\.create',
            r'<input type="hidden" name="braintree_token"', r'<input type="hidden" name="payment_method_nonce"'
        ]
        for indicator in braintree_indicators:
            if re.search(indicator, str(response.content), re.IGNORECASE):
                return True
    except Exception as e:
        pass
    return False

def check_stripe_usage(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False
        soup = BeautifulSoup(response.content, 'html.parser')
        stripe_indicators = [
            r'stripe\.js', r'stripe\.com', r'Stripe\.setPublishableKey', r'StripeCheckout', r'StripeElements',
            r'elements\.create$$', r'stripeTokenHandler', r'Stripe\.confirmCardPayment', r'Stripe\.confirmCardSetup',
            r'Stripe\.confirmPaymentMethod'
        ]
        for indicator in stripe_indicators:
            if re.search(indicator, str(response.content), re.IGNORECASE):
                return True
    except Exception as e:
        pass
    return False

def check_captcha_cloudflare(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return True
        soup = BeautifulSoup(response.content, 'html.parser')
        captcha_indicators = [
            r'captcha', r'recaptcha', r'g-recaptcha', r'hCaptcha', r'cloudflare', r'cf-browser-verification',
            r'checking your browser before accessing', r'verify you are human', r'I am not a robot',
            r'please verify', r'security check'
        ]
        for indicator in captcha_indicators:
            if re.search(indicator, str(response.content), re.IGNORECASE):
                return True
    except Exception as e:
        pass
    return False

def process_search_term(base, term, page, payment_processor):
    if payment_processor == 'stripe':
        query = f'{base}{term} inurl:/donate intext:stripe'
    elif payment_processor == 'braintree':
        query = f'{base}{term} inurl:/donate intext:braintree'
    else:
        return []
    search_url = f'https://www.bing.com/search?q={query}&first={page*10}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        return []
    soup = BeautifulSoup(response.content, 'html.parser')
    links = soup.find_all('a')
    donation_sites = []
    for link in links:
        href = link.get('href')
        if href:
            absolute_url = urljoin(search_url, href)
            parsed_url = urlparse(absolute_url)
            if 'donate' in parsed_url.path:
                if payment_processor == 'stripe' and check_stripe_usage(absolute_url) and not check_captcha_cloudflare(absolute_url):
                    donation_sites.append((absolute_url, payment_processor))
                elif payment_processor == 'braintree' and check_braintree_usage(absolute_url) and not check_captcha_cloudflare(absolute_url):
                    donation_sites.append((absolute_url, payment_processor))
    return donation_sites

def search_donation_sites():
    query_base = [
        'donate to ', 'support ', 'fund ', 'help ', 'sponsor ', 'finance ', 'contribute to ', 'give to ', 'aid ',
        'back ', 'promote ', 'advance ', 'boost ', 'assist '
    ]
    search_terms = [
        'charity', 'nonprofit', 'cause', 'project', 'campaign', 'fundraiser', 'donation', 'contribution', 'support',
        'organization', 'foundation', 'initiative', 'program', 'effort', 'mission', 'goal', 'objective'
    ]
    stripe_sites = set()
    braintree_sites = set()
    with ThreadPoolExecutor(max_workers=20) as executor:
        page = 1
        while True:
            futures = []
            for base in query_base:
                for term in search_terms:
                    futures.append(executor.submit(process_search_term, base, term, page, 'stripe'))
                    futures.append(executor.submit(process_search_term, base, term, page, 'braintree'))
            for future in as_completed(futures):
                sites = future.result()
                for site, payment_processor in sites:
                    if payment_processor == 'stripe' and site not in stripe_sites:
                        stripe_sites.add(site)
                        with open('url.txt', 'a') as file:
                            file.write(site + '\n')
                        send_to_telegram(f"/url {site}")
                    elif payment_processor == 'braintree' and site not in braintree_sites:
                        braintree_sites.add(site)
                        with open('b3.txt', 'a') as file:
                            file.write(site + '\n')
                        send_to_telegram(f"/url {site}")
            page += 1

if __name__ == "__main__":
    search_donation_sites()
