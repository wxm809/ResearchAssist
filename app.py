import os
import OpenAI
from llama_index import Document, GPTSimpleVectorIndex, SimpleNodeParser
from multiprocessing import Process
from flask import Flask, jsonify, request, render_template
import json
import pickle
import sqlite3

CONNECTION = sqlite3.connect('researchassist.db')
CURSOR = CONNECTION.cursor()
class Conversation:
    def __init__(self, subject, index):
        self.index = index
        self.subject = subject
        self.messages = []
    def index(self):
        return self.index
    def messages(self):
        return self.messages
    def addMessage(self, message):
        self.messages.append(message)
    def subject(self):
        return self.subject

class User:
    def __init__(self, id):
        self.id = id 
        self.conversations = {}
    def id(self):
        return self.user_id
    def constructIndex(self, request):
        if(request.files.getlist('pdfs') == []):
            return None
        documents = [Document(t) for t in request.files.getlist('pdfs')] #get pdfs from request and read them into a list of Documents
        index = GPTSimpleVectorIndex(SimpleNodeParser().get_nodes_from_documents(documents)) #create index from documents
        self.conversations.put(request.SOMETHING, Conversation(request.SOMETHIGNG_ELSE, index)) #TODO: MAKE CONVERSATION ID DEPEND ON COOKIES 
        return index
    def conversations(self):
        return self.conversations

app = Flask(__name__)
app.debug(True)

def putUser(user):
    CURSOR.execute('INSERT INTO users VALUES(?)', (user.id,))

def upload(request):
    user = User(request.cookies.get('user_id'))

    index = user.constructIndex(request)
    return index
    
