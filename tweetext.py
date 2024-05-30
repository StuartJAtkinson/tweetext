import colorama
import requests
import platform
import argparse
from pathlib import Path
import asyncio
import sys
import re
import urllib3
from colorama import Fore, Back
from tqdm import tqdm
from time import sleep
from aiohttp import ClientSession
import random
from requests_futures.sessions import FuturesSession
import bs4
from concurrent.futures import as_completed

from itertools import cycle
from shutil import get_terminal_size
from threading import Thread

class Loader:
    def __init__(self, desc="Loading...", end="Done!", timeout=0.1):
        """
        A loader-like context manager
        Args:
            desc (str, optional): The loader's description. Defaults to "Loading...".
            end (str, optional): Final print. Defaults to "Done!".
            timeout (float, optional): Sleep time between prints. Defaults to 0.1.
        """
        self.desc = desc
        self.end = end
        self.timeout = timeout

        self._thread = Thread(target=self._animate, daemon=True)
        self.steps = ["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"]
        self.done = False

    def start(self):
        self._thread.start()
        return self

    def _animate(self):
        for c in cycle(self.steps):
            if self.done:
                break
            print(f"\r{self.desc} {c}", flush=True, end="")
            sleep(self.timeout)

    def __enter__(self):
        self.start()

    def stop(self):
        self.done = True
        cols = get_terminal_size((80, 20)).columns
        print("\r" + " " * cols, end="", flush=True)
        print(f"\r{self.end}", flush=True)

    def __exit__(self, exc_type, exc_value, tb):
        # handle exceptions with those variables ^
        self.stop()

# checks the status of a given url
async def checkStatus(url, session: ClientSession, sem: asyncio.Semaphore, proxy_server):
    async with sem:
        if proxy_server == '':
            async with session.get(url) as response:
                return url, response.status
        else:
            async with session.get(url, proxy = proxy_server) as response:
                return url, response.status
        
    
# controls our async event loop
async def asyncStarter(url_list, semaphore_size, proxy_list):

    status_list = []
    headers = {'user-agent':'Mozilla/5.0 (compatible; DuckDuckBot-Https/1.1; https://duckduckgo.com/duckduckbot)'}
    proxy_server = chooseRandomProxy(proxy_list)
    
    # this will wrap our event loop and feed the the various urls to their async request function.
    async with ClientSession(headers=headers) as a_session:
        
        sem = asyncio.Semaphore(semaphore_size)

        # if aiohttp throws an error it will be caught and we'll try again up to 5 times
        for x in range(0,5):
            try:
                status_list = await asyncio.gather(*(checkStatus(u, a_session, sem, proxy_server) for u in url_list))
                break
            except:
                proxy_server = chooseRandomProxy(proxy_list)
                print(f"Error. Trying a different proxy: {proxy_server}")
                status_list = []
                
    # return a list of the results 
    if status_list != []:   
        return status_list
    else:
        print("There was an error with aiohttp proxies. Please Try again")
        exit()

def chooseRandomProxy(proxy_list):
    if proxy_list != []:
        return "http://" + proxy_list[random.randint(0, len(proxy_list)-1)]
    else:
        return ''

colorama.init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Parse arguments passed in from command line
parser = argparse.ArgumentParser()
parser.add_argument('-u', '--username', required=True, default='')
parser.add_argument('-from', '--fromdate', required=False, default='')
parser.add_argument('-to', '--todate', required=False, default='')
parser.add_argument('--batch-size', type=int, required=False, default=300, help="How many urls to examine at once.")
parser.add_argument('--semaphore-size', type=int, required=False, default=50, help="How many urls(from --batch-size) to query at once. Between 1 and 50")
parser.add_argument('--proxy-file', required=False, default='', help="A list of proxies the script will rotate through")
parser.add_argument('--batch-delay', type=float, required=False, default=2, help="Delay between batches in seconds.")
args = vars(parser.parse_args())

account_name = args['username']
from_date = args['fromdate']
to_date = args['todate']
batch_size = args['batch_size']
semaphore_size = args['semaphore_size']
proxy_file = args['proxy_file']
batch_delay = args['batch_delay']

proxy_list = []
if proxy_file != '':
    with open(proxy_file, "r") as f:
        for x in f.readlines():
            proxy_list.append(x.split("\n")[0])


remove_list = ['-', '/']
from_date = from_date.translate({ord(x): None for x in remove_list})
to_date = to_date.translate({ord(x): None for x in remove_list})
account_url = f"https://twitter.com/{account_name}"
headers = {'User-Agent': 'Mozilla/5.0 (compatible; DuckDuckBot-Https/1.1; https://duckduckgo.com/duckduckbot)'}

# Check status code
account_response = requests.get(account_url, headers=headers, allow_redirects=False)
status_code = account_response.status_code

if status_code == 200:
    print(Back.GREEN + Fore.WHITE + f"Account is ACTIVE")
elif status_code == 302:
    print(Back.RED + Fore.WHITE + f"Account is SUSPENDED. This means all of "
          f"{Back.WHITE + Fore.RED + account_name + Back.RED + Fore.WHITE}'s Tweets will be "
          f"downloaded.")
elif status_code ==429:
    print(Back.RED + Fore.WHITE + f"Respose Code 429: Too Many Requests. Your traffic to Twitter is being limited and results of this script will not be accurate")
    exit()
else:
    print(Back.RED + Fore.WHITE + f"No one currently has this handle. Twayback will search for a history of this "
          f"handle's Tweets.")
sleep(1)


wayback_cdx_url = f"https://web.archive.org/cdx/search/cdx?url=twitter.com/{account_name}/status" \
                  f"&matchType=prefix&filter=statuscode:200&mimetype:text/html&from={from_date}&to={to_date}"
cdx_page_text = requests.get(wayback_cdx_url).text

if len(re.findall(r'Blocked', cdx_page_text
