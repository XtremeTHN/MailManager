import threading
import os
import pickle
import sqlite3

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from gi.repository import GObject

# GObject signals are defined with the __gsignals__ property
# __gsignals__ = {
#    "example-signal": (RunType, ReturnParameter, (ArgumentsType))
# }
#
#
# More info https://python-gtk-3-tutorial.readthedocs.io/en/latest/objects.html#create-new-signals:~:text=loop%20and%20Signals-,23.2.2.%20Create%20new%20signals,-New%20signals%20can

SCOPES=['https://mail.google.com/']
ROOT_DIR=os.path.join(os.getenv('HOME'), "Documents", "Projects", "Linux", "Gmail", 'src')
CREDENTIALS_FOLDER=os.path.join(ROOT_DIR, "credentials")
SECRETS_FILE=os.path.join(CREDENTIALS_FOLDER, "credentials.json")
PICKLE_FILE=os.path.join(CREDENTIALS_FOLDER, "token.pickle")

DATABASE_PATH=os.path.join(ROOT_DIR, "database", "emails.db")

class GmailDatabase:
    def __init__(self, db_path: str):
        self.path = db_path
        self.database = sqlite3.connect(db_path)
        self.cursor = self.database.cursor()
        
        self.database.execute("""
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "Email" (
	"ID"	INTEGER NOT NULL,
	"Subject"	TEXT,
	"Body"	TEXT NOT NULL,
	"SenderName"	TEXT NOT NULL,
	"SenderIcon"	TEXT,
	"SenderEmail"	TEXT NOT NULL,
	"RecieverName"	TEXT NOT NULL,
	"RecieverEmail"	TEXT NOT NULL,
	PRIMARY KEY("ID")
);
COMMIT;
""")
    def get_emails(self):
        return self.cursor.fetchall()
        
    def get_email(self, id):
        self.database.execute(f"SELECT * FROM Email WHERE ID = {id};")
        return self.cursor.fetchall()
    
    def get_last_email(self):
        self.database.execute("SELECT * FROM Email ORDER BY column DESC LIMIT 1;")
    
    def add_email(self, id, body, sender_name, sender_icon, sender_email, reciever_name, reciever_email, subject=""):
        self.database.execute(f"""
INSERT INTO email(ID, Subject, Body, SenderName, SenderIcon, SenderEmail, RecieverName, RecieverEmail) VALUES({id},{subject},{body},{sender_name},{sender_icon},{sender_email},{reciever_name},{reciever_email});
""")
    
        
class Gmail(GObject.GObject, threading.Thread):
    __gsignals__ = {
        'authentication-start': (GObject.SignalFlags.RUN_LAST,
                                 None, ()),
        'authentication-finish': (GObject.SignalFlags.RUN_LAST,
                                  None, ()),
        
        'emails-download-start': (GObject.SignalFlags.RUN_LAST,
                                  None, ()),
        'emails-download-finish': (GObject.SignalFlags.RUN_LAST,
                                   None, ()),
    }

    stack=GObject.Property(type='str', default="", flags=GObject.ParamFlags.READABLE)
    def __init__(self):
        """
            Inits the Gmail handler

            Connects to the gmail api and authenticate the user, in a separeted thread

            Signals:
                authentication-start: Emited when the authentication is started. Accepts Gmail Object. Returns None
                authentication-finish: Emited when the authentication is finished. Accepts Gmail Object. Returns None

                emails-download-start: Emited when the download of the emails is started. Accepts no arguments. Returns None
                emails-dnownload-finish: Emited when the download of the emails has been finish. Accepts no arguments. Returns None
        """
        GObject.GObject.__init__(self)
        threading.Thread.__init__(self, target=self.auth)

        self.gmail = None
        self.database = GmailDatabase(DATABASE_PATH)

        self.start()
    
    def _add_to_prog(self, msg):
        self.set_property("stack", str(msg))

    def auth(self):
        """
            Authenticates user to the gmail server
            Do not exec this function, cuz it is executed in __init__ func

            Emits:
                authentication-start
                authentication-finish

            Arguments:
                None

            Returns:
                None
        """
        self.emit("authentication-start")
        creds = None
        self._add_to_prog("Checking if there's credentials...")
        if os.path.exists(PICKLE_FILE):
            with open(PICKLE_FILE, 'rb') as file:
                creds = pickle.load(file)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self._add_to_prog("Requesting a new session...")
                creds.refresh(Request())
            else:
                self._add_to_prog("Opening OAuth window...")
                flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
                creds = flow.run_local_server(port=8080)
            with open(PICKLE_FILE, "wb") as token:
                self._add_to_prog("Saving credentials...")
                pickle.dump(creds, token)
        
        self._add_to_prog("Connecting to the Gmail API...")
        self.gmail = build('gmail', 'v1', credentials=creds)

        self._add_to_prog("Authentiation finished")
        self.emit('authentication-finish')
    
    # def emails(self):
    #     res = self.gmail.users().messages().list(userId='me').execute()
    #     messages = res.get('messages')

    #     for msg in messages:
    #         txt = self.gmail.users().messages().get(userId='me', id=msg['id']).execute()
    #         print(txt)
    
    def update_database(self):
        """
            Updates/Set's emails info into the database

            Emits:
                emails-download-start
                emails-download-finish
        """
        res = self.gmail.users().messages().list(userId='me').execute()
