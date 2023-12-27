import threading
import os
import pickle
import sqlite3
import base64

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
ROOT_DIR=os.path.join(os.getcwd(), 'src')
CREDENTIALS_FOLDER=os.path.join(ROOT_DIR, "credentials")
SECRETS_FILE=os.path.join(CREDENTIALS_FOLDER, "credentials.json")
PICKLE_FILE=os.path.join(CREDENTIALS_FOLDER, "token.pickle")

os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

if os.path.exists(CREDENTIALS_FOLDER) is False:
    print("You should get some credentials from the Google Cloud Platform Console")
    print("Exiting...")
    sys.exit(1)

DATABASE_PATH=os.path.join(ROOT_DIR, "database", "emails.db")
print(DATABASE_PATH)

class GmailDatabase:
    def __init__(self, db_path: str):
        self.path = db_path
        self.database = sqlite3.connect(db_path)
        self.cursor = self.database.cursor()
        
        self.cursor.execute("BEGIN TRANSACTION;")
        self.cursor.execute("""
CREATE TABLE IF NOT EXISTS "Email" (
	"ID"	INTEGER,
	"Subject"	TEXT,
	"Body"	TEXT NOT NULL,
	"SenderName"	TEXT NOT NULL,
	"SenderIcon"	TEXT,
	"SenderEmail"	TEXT NOT NULL,
	"RecieverName"	TEXT NOT NULL,
	"RecieverEmail"	TEXT NOT NULL,
	PRIMARY KEY("ID" AUTOINCREMENT)
);
""")
        self.cursor.execute("COMMIT;")
    def get_emails(self):
        return self.cursor.fetchall()
        
    def get_email(self, id):
        self.cursor.execute(f"SELECT * FROM Email WHERE ID = {id};")
        return self.cursor.fetchall()
    
    def get_last_email(self):
        self.cursor.execute("SELECT * FROM Email ORDER BY column DESC LIMIT 1;")
    
    def add_email(self, body, sender_name, sender_icon, sender_email, reciever_name, reciever_email, subject=""):
        self.cursor.execute(f"""
INSERT INTO Email VALUES(NULL, "{subject}","{body}","{sender_name}","{sender_icon}","{sender_email}","{reciever_name}","{reciever_email}");
""")
        self.database.commit()
        print("added email")
    
        
class Gmail(GObject.GObject, threading.Thread):
    __gsignals__ = {
        'authentication-start': (GObject.SignalFlags.RUN_LAST,
                                 None, ()),
        'authentication-finish': (GObject.SignalFlags.RUN_LAST,
                                  None, ()),
        
        'emails-download-start': (GObject.SignalFlags.RUN_LAST,
                                  None, ()),
        'emails-download-position': (GObject.SignalFlags.RUN_LAST,
                                     None, (float,)),
        'emails-download-finish': (GObject.SignalFlags.RUN_LAST,
                                   None, ()),

        # 'email-added-to-database', (GObject.SignalFlags.RUN_LAST,
        #                             None, ())
    }

    stack=GObject.Property(type=GObject.TYPE_STRING, default="")
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
        self.database: sqlite3.Connection = None

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
    
    def _database_item(self, rq_id, res: dict, exc):
        try:
            payload=res['payload']
            headers=payload['headers']

            for d in headers:
                if d['name'] == 'Subject':
                    subject = d['value']
                if d['name'] == 'From':
                    sender = d['value']
            
            parts = payload.get('parts')[0]
            data = parts['body']['data'].replace("-","+").replace("_","/")

            print("adding to database", sender)
            self.database.add_email(data, sender, "user-symbolic", "example@gmail.com", "axel", "example", subject=subject)
        except Exception as e:
            print("Exception: ",e)
    
    def start_database(self):
        """
        Initializes the database for the Gmail object.
        Use this method if you need to call the update_database method in another thread

        Returns:
            None
        """
        if self.database is not None:
            self.database.close()
        self.database = GmailDatabase(DATABASE_PATH)

    def update_database(self):
        """
            Updates/Set's emails info into the database
            Use this method in the same thread that you called start_database method
            If Gmail.database is None, it will initialize the database

            Emits:
                emails-download-start
                emails-download-finish
        """
        if self.database is None:
            self.start_database()

        self._add_to_prog("")
        res = self.gmail.users().messages().list(userId='me', maxResults=50).execute()
        messages = res.get('messages')

        bulk = self.gmail.new_batch_http_request()
        for msg in messages:
            bulk.add(self.gmail.users().messages().get(userId='me', id=msg['id']), callback=self._database_item)
        bulk.execute()