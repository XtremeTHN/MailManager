import threading
import os
import sys
import pickle
import sqlite3
import re

import keyring
from cryptography.fernet import Fernet

if keyring.get_password("com.github.Axel.MailManager", "axel") is None:
    keyring.set_password("com.github.Axel.MailManager", "axel", Fernet.generate_key().decode("utf-8"))

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from datetime import datetime
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

        self._decrypt()
        self.database = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.database.cursor()
        
        self.cursor.execute("BEGIN TRANSACTION;")
        self.cursor.execute("""
CREATE TABLE IF NOT EXISTS "Email" (
    "ID"	INTEGER,
    "MSGID"	TEXT NOT NULL,
    "SenderName"	TEXT NOT NULL,
    "SenderIcon"	TEXT,
    "SenderEmail"	TEXT NOT NULL,
    "RecieverName"	TEXT NOT NULL,
    "RecieverEmail"	TEXT NOT NULL,
    "Date"	TEXT NOT NULL,
    "Subject"	TEXT,
    "Body"	TEXT NOT NULL,
    PRIMARY KEY("ID" AUTOINCREMENT)
);
""")
        self.cursor.execute("COMMIT;")
    
    def _decrypt(self):
        """
        Decrypts the database if it is encrypted
        This should not be called manually, __init__ calls it automatically

        Parameters:
            self (GmailDatabase): The current instance of the class.
        
        Returns:
            None
        """
        if os.path.exists(DATABASE_PATH + '.enc') is True:
            with open(DATABASE_PATH + '.enc', 'rb') as file:
                data = file.read()
            f = Fernet(keyring.get_password("com.github.Axel.MailManager", "axel"))
            decrypted = f.decrypt(data)
            with open(DATABASE_PATH, 'wb') as file:
                file.write(decrypted)
            print(DATABASE_PATH + '.enc')
            os.remove(DATABASE_PATH + '.enc')

    def _encrypt(self):
        """
        Encrypts the database if it is not encrypted
        This should not be called manually, a signal will call this method when the app is closed

        Parameters:
            self (GmailDatabase): The current instance of the class.
        
        Returns:
            None
        """
        with open(DATABASE_PATH, 'rb') as file:
            data = file.read()
        f = Fernet(keyring.get_password("com.github.Axel.MailManager", "axel"))
        encrypted = f.encrypt(data)
        with open(DATABASE_PATH + '.enc', 'wb') as file:
            file.write(encrypted)
        os.remove(DATABASE_PATH)

    def get_emails(self) -> list[tuple]:
        """
        Retrieves all emails from the database.

        Parameters:
            self (GmailDatabase): The current instance of the class.

        Returns:
            list[tuple]: A list of all emails retrieved from the database.
        """
        return self.cursor.fetchall()
        
    def get_email(self, id) -> list[tuple]:
        """
        Get the email from the database based on the given ID.

        Parameters:
            id (int): The ID of the email to retrieve. If -1, retrieve the latest email.

        Returns:
            list[tuple]: A list of email(s) retrieved from the database.
        """
        if id == -1:
            self.cursor.execute(f"SELECT * FROM Email ORDER BY ID DESC LIMIT 1;")
            return self.cursor.fetchall()
        else:
            self.cursor.execute(f"SELECT * FROM Email WHERE ID = {id};")
            return self.cursor.fetchall()
    
    def get_last_email(self):
        """
        Retrieves the last email from the database

        Returns:
            None.
        """
        self.cursor.execute("SELECT * FROM Email ORDER BY column DESC LIMIT 1;")
    
    def add_email(self, 
                  msg_id, 
                  sender_name, 
                  sender_icon, 
                  sender_email, 
                  reciever_name, 
                  reciever_email, 
                  date, body, subject=""):
        """
        Inserts an email into the Email table in the database.

        Parameters:
            msg_id (str): The ID of the email message.
            sender_name (str): The name of the sender.
            sender_icon (str): The icon of the sender.
            sender_email (str): The email address of the sender.
            receiver_name (str): The name of the receiver.
            receiver_email (str): The email address of the receiver.
            date (str): The date the email was sent.
            body (str): The body of the email.
            subject (str, optional): The subject of the email. Defaults to "".

        Returns:
            None
        """

        
        self.cursor.execute(f"""
INSERT INTO Email VALUES(NULL, "{msg_id}", "{sender_name.replace('"', '')}","{sender_icon}","{sender_email}","{reciever_name.replace('"', '')}","{reciever_email}", "{date}", "{subject.replace('"', '')}","{body}");
""")

    def is_empty(self):
        """
        Checks if the database is empty by executing a SQL query and returning
        True if the count of rows is equal to 0.

        Parameters:
            self (object): The object instance.

        Returns:
            bool: True if the table is empty, False otherwise.
        """
        return self.cursor.execute("SELECT count(*) FROM Email;").fetchone()[0] == 0

    def save(self):
        """
        Saves current changes to the database

        Parameters:
            self (object): The object instance.
        
        Returns:
            None
        """
        self.database.commit()
    
    def close(self):
        """
        Closes the database

        Parameters:
            self (object): The object instance.
        
        Returns:
            None
        """
        self.database.close()
        
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
        self.oauth = None
        self.database: GmailDatabase = None

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

        self._add_to_prog("Authentication finished")
        self.emit('authentication-finish')    

    def parse_email(self, res: dict):
        """
        Parses an email response and extracts relevant information to store in the database.

        Parameters:
            res (dict): The email response dictionary.

        Returns:
            None
        """
        try:
            payload=res['payload']
            headers=payload['headers']

            id = res['id']
            for d in headers:
                if d['name'] == 'Subject':
                    subject = d['value']
                if d['name'] == 'From':
                    # Sender name comes in this format "Name <email@server.com>". So we just split the string with this character "<".
                    sender_data: list[str] = d['value'].split('<')

                    # sender[0] = Name and sender[1] = email@server.com

                    sender = [sender_data[0], sender_data[1].split('>')[0]]
                if d['name'] == 'To':
                    # Same as above
                    try:
                        reciever_data: list[str] = d['value'].split('<')
                        reciever = [reciever_data[0], reciever_data[1].split('>')[0]]
                    except:
                        reciever = [d['value'], d['value']]
                if d['name'] == 'Date':
                    created_time = d['value']

            parts = list(filter(lambda x: x['mimeType'] == 'text/html', payload.get('parts')))[0]

            if parts is not None:
                data = parts['body']['data'].replace("-","+").replace("_","/")
            else:
                parts = payload.get('parts')[0]
                data = parts['body']['data'].replace("-","+").replace("_","/")

            self.database.add_email(
                id, 
                sender[0], 
                "avatar-default", 
                sender[1],
                reciever[0],
                reciever[1],
                created_time, 
                data, subject=subject
            )

        except Exception as e:
            print(f"\n{type(e).__name__}: {e}")
            return False

    def start_database(self):
        """
        Initializes the database for the Gmail object.
        Use this method if you need to manipulate the database

        Returns:
            GmailDatabase: The database object
        """
        if self.database is not None:
            self.database.database.close()
        self.database = GmailDatabase(DATABASE_PATH)

        return self.database

    def get_chunk_of_emails(self, chunk: int, nextPageToken:str=None, **parameters):
        """
        Retrieves a chunk of emails from the Gmail API.

        Args:
            chunk (int): The number of emails to retrieve.
            nextPageToken (str, optional): The token for the next page of emails. Defaults to None.
            **parameters: Additional parameters to be passed to the API request.

        Returns:
            dict: The response from the API containing the retrieved emails.
        """
        return self.gmail.users().messages().list(userId='me', maxResults=chunk, pageToken=nextPageToken, **parameters).execute()

    def partial_sync(self):
        ...
        

    def _get_all_emails_from_gmail(self, messages, res):
        while True:
            print("INFO: Going back into loop...")
            for msg in messages:
                print(f"INFO: Parsing email {msg['id']}.", end='\r')
                self.parse_email(self.gmail.users().messages().get(userId='me', id=msg['id']).execute())
            print('\nINFO: Getting next chunk...')
            if 'nextPageToken' not in res:
                break
            else:
                self.database.save()
                res = self.get_chunk_of_emails(500, res['nextPageToken'])
                messages = res.get('messages')
                email_pos = 0
                pos += 500

    def synchronize(self):
        """
            Populates the database with emails info
            This method will always initialize a new GmailDatabase instance. If Gmail.database is not None, the database will be closed

            Emits:
                emails-download-start
                emails-download-finish
        """
        if self.database is not None:
            print("WARNING: Overwriting Gmail.database object. Cause: Exception ocurred")
            try:
                self.database.close()
            except:
                self.database = None

        self.start_database()

        self._add_to_prog("")
        res = self.get_chunk_of_emails(500)
        messages = res.get('messages')


        try:
            self._get_all_emails_from_gmail(messages, res)
        except:
            print("\nFATAL: Error while populating database. Saving current changes...")
            self.database.save()
    
        print("INFO: Database population finished")
        self.database.cursor.execute("SELECT * FROM Email ORDER BY ID DESC;")
        self.database.save()