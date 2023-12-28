from modules.gmail import Gmail
from bs4 import BeautifulSoup

import base64
import time
import os

from datetime import datetime


def handle_finish(gm: Gmail):
    # last_email = list(gm.database.get_email(-1)[0])
    # last_email[-1] = base64.b64decode(last_email[-1]).decode()

    # soup = BeautifulSoup(last_email[-1], 'lxml')
    # last_email[-1] = soup.body()

    gm.synchronize()

gm = Gmail()

gm.start_database()
gm.database._encrypt()

gm.start()
gm.connect('authentication-finish', handle_finish)