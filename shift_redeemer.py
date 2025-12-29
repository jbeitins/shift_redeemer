#!/usr/bin/env python3
import requests, pickle, os, logging, getpass, re
from bs4 import BeautifulSoup as bs

# Config
DRY_RUN = False
CONFIG = ".config/shift_redeemer"
PLATFORM = 'steam'
URLS = [
	'https://www.ign.com/wikis/borderlands-4/Borderlands_4_SHiFT_Codes',
	'https://mentalmars.com/game-news/borderlands-4-shift-codes/',
	]

os.makedirs(CONFIG, exist_ok=True)

log = logging.getLogger()
log.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s"))
log.addHandler(ch)

fh = logging.FileHandler(f"{CONFIG}/shift_redeemer.log")
fh.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s"))
fh.addFilter(lambda record: setattr(record, "msg", str(record.msg).replace("\n", " ").replace("\r", "")) or True)
log.addHandler(fh)

class Redeemer:
	def __init__(self):
		self.cookie_file = f'{CONFIG}/shift_cookies.pkl'
		self.history_file = f'{CONFIG}/shift_codes.txt'
		self.session = requests.Session()
		self.base_url = "https://shift.gearboxsoftware.com"
		self.csrf_token = None
		self.redeemed_history = self._load_history()
		
		self.session.headers.update({
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
			'Referer': self.base_url
		})

	def _load_history(self):
		"""Loads the set of previously processed codes."""
		if not os.path.exists(self.history_file):
			return set()
		with open(self.history_file, 'r') as f:
			return set(line.strip() for line in f if line.strip())

	def _save_to_history(self, code):
		"""Appends a code to the history file and updates memory."""
		self.redeemed_history.add(code)
		try:
			with open(self.history_file, 'a') as f:
				f.write(f"{code}\n")
		except Exception as e:
			log.warning(f"Failed to save history: {e}")

	def _extract_csrf_token(self, html_content):
		soup = bs(html_content, 'html.parser')
		token = soup.find('meta', {'name': 'csrf-token'})
		if token and token.get('content'):
			self.csrf_token = token['content']
			return token['content']
		
		token_input = soup.find('input', {'name': 'authenticity_token'})
		if token_input:
			self.csrf_token = token_input.get('value')
			return self.csrf_token
		return None

	def _save_session(self):
		try:
			with open(self.cookie_file, 'wb') as f:
				pickle.dump(self.session.cookies, f)
		except Exception as e:
			log.error(f"Failed to save session: {e}")

	def _load_session(self):
		if not os.path.exists(self.cookie_file):
			return False
		try:
			with open(self.cookie_file, 'rb') as f:
				cookies = pickle.load(f)
				self.session.cookies.update(cookies)
			return True
		except Exception:
			return False

	def check_auth(self):
		try:
			response = self.session.get(f"{self.base_url}/home")
			self._extract_csrf_token(response.text)
			return "Sign Out" in response.text
		except:
			return False

	def login(self):
		if self._load_session():
			if self.check_auth():
				return True
			log.info("Saved session expired")

		email = input("E-mail: ")
		password = getpass.getpass("Password: ")
		
		print(f"Logging in as {email}...")
		response = self.session.get(f"{self.base_url}/home")
		token = self._extract_csrf_token(response.text)
		
		if not token:
			log.error("Failed to get CSRF token")
			return False

		payload = {
			'authenticity_token': token,
			'user[email]': email,
			'user[password]': password,
			'commit': 'Sign In'
		}

		response = self.session.post(f"{self.base_url}/sessions", data=payload)

		if response.status_code == 200 and "Sign Out" in response.text:
			print("Login successful!")
			self._extract_csrf_token(response.text)
			self._save_session()
			return True
		else:
			print("Login failed")
			return False
		
	def fetch_codes(self):
		codes = set()
		pattern = re.compile(r'\b[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}\b')
		
		for url in URLS:
			try:
				response = self.session.get(url, timeout=10)
				soup = bs(response.content, 'html.parser')
				for table in soup.find('table'):
					table_text = table.get_text(separator=" ").upper()
					found = pattern.findall(table_text)
					codes.update(found)
			except Exception as e:
				log.error(f"Failed to fetch codes: {e}")
				return []
		return list(codes)

	def redeem_code(self, code):
		code = code.strip()
		
		if DRY_RUN:
			self._save_to_history(code)
			return
		
		# 1. Skip if already processed
		if code in self.redeemed_history:
			return

		log.info(f"Attempting to redeem: {code}")
		
		if not self.csrf_token:
			log.error("No CSRF token")
			return

		ajax_headers = {
			'X-CSRF-Token': self.csrf_token,
			'X-Requested-With': 'XMLHttpRequest',
			'Accept': '*/*;q=0.5, text/javascript, application/javascript'
		}
		
		# 2. Check status
		try:
			check_url = f"{self.base_url}/entitlement_offer_codes?code={code}"
			response = self.session.get(check_url, headers=ajax_headers)
		except Exception as e:
			log.error(f"Network error: {e}")
			return

		soup = bs(response.text, 'html.parser')

		# 3. Find form
		forms = soup.find_all('form')
		form = None
		for form in forms:
			if PLATFORM.lower() in str(form).lower():
				form = form
				break
		
		if not form:
			log.error(response.text.strip("{}") or "Code validation failed")
			return

		# 4. Submit Redemption
		redemption_url = form.get('action')
		if not redemption_url.startswith('http'): redemption_url = self.base_url + redemption_url

		data = {}
		for input_tag in form.find_all('input'):
			if input_tag.get('name'): data[input_tag['name']] = input_tag.get('value', '')

		try:
			redeem_response = self.session.post(redemption_url, data=data, headers=ajax_headers)
			
			try: message = redeem_response.json().get('text', '') 
			except: message = bs(redeem_response.text, 'html.parser').find('div', class_='alert').get_text().strip()

			if 'redeemed' in message:
				log.info(f"{message}")
				self._save_to_history(code)
			else:
				log.warning(f"{message}")
				
		except Exception as e:
			log.error(f"Error parsing response")

if __name__ == "__main__":
	redeemer = Redeemer()
	
	if redeemer.login():
		new_codes = redeemer.fetch_codes()
		upcoming_codes = [c for c in new_codes if c not in redeemer.redeemed_history]
		for code in upcoming_codes:
			redeemer.redeem_code(code)
