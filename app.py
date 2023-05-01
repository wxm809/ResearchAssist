from flask import Flask, jsonify, request, render_template, redirect, url_for, make_response
import json
import pickle
import sqlite3
from classes import User, Conversation
from llama_index import GPTSimpleVectorIndex
import os
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
import uuid

CONNECTION = sqlite3.connect('researchassist.db')
CURSOR = CONNECTION.cursor()
CURSOR.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, data BLOB)')
CONNECTION.commit()

class InsertedExistingUserException(Exception):
    pass

class UserNotInDatabaseException(Exception):
    pass

class ConversationNotFoundException(Exception):
    pass

app = Flask(__name__)

socketio = SocketIO(app)

def putUser(user: User):
    userData = pickle.dumps(user)
    try:
        CURSOR.execute('INSERT INTO users (id, data) VALUES (?, ?)', (user.id, userData))
        CONNECTION.commit()
    except sqlite3.IntegrityError:
        raise InsertedExistingUserException

def updateUser(user: User):
    userData = pickle.dumps(user)
    CURSOR.execute('UPDATE users SET data=? WHERE id=?', (userData, user.id))
    CONNECTION.commit()
    if(CURSOR.rowcount == 0):
        raise UserNotInDatabaseException

def getUser(id: int) -> User:
    CURSOR.execute('SELECT data FROM users WHERE id=?', (id,))
    userData = CURSOR.fetchone()[0]
    if userData is None:
        raise UserNotInDatabaseException
    return pickle.loads(userData)


@app.route('/upload', methods=['POST'])
def handleFileUpload():
    id = request.cookies.get('user_id')
    files = request.files.getlist('files')
    subject = request.form('subject')
    try:
        user = getUser(id)
    except UserNotInDatabaseException:
        print("uh oh")
        if not id:
            print("no id generated")
            return newUser()
        else:
            print("user never put in database, but id exists")
            user = User(id)
            putUser(user)
    for file in files:
        # Check if the file has a PDF file extension
        if file and file.filename.endswith('.pdf'):
            # Generate a secure filename and save the file to disk
            filename = secure_filename(file.filename)
        else:
            return redirect(url_for('index'))
    user.constructGraphFromRequest(subject, files, disable = True)
    updateUser(user)
    # generate redirect to upload-complete
    return redirect(url_for('/upload-complete'))

def newUser():
    user_id = str(uuid.uuid4())
    response = make_response(render_template('index.html'))
    putUser(User(user_id))
    response.set_cookie('user_id', user_id)
    return response

@app.route('/')
def index():
    user_id = request.cookies.get('user_id')
    if not user_id:
        return newUser()
    else:
        return render_template('index.html')

@app.route('/upload-complete')
def uploadComplete():
    user_id = request.cookies.get('user_id')
    if not user_id:
        return newUser()
    else:
        user = getUser(user_id)
        documents = user.conversations
        return render_template("upload-complete.html")

def ask() -> str:
    id = request.cookies.get('user_id')
    user = getUser(id) #watch out for UserNotInDatabaseException when calling ask!
    conversation = user.conversations.get(request.SOMETHING)
    if conversation is None:
        raise ConversationNotFoundException
    userPrompt = request.SOMETHING_ELSE
    response = ""

def clearDatabase():
    CURSOR.execute('DELETE FROM users')
    CONNECTION.commit()

def mainFn():
    user = User(5000)
    user.conversations['test'] = Conversation('test', None, None, True)
    try:
        putUser(user)
    except InsertedExistingUserException:
        print('User already exists')
    user = getUser(5000)
    print(user.conversations['test'].subject)

if __name__ == '__main__':
    DEBUG=False
    if DEBUG:
        clearDatabase()
        mainFn()
    socketio.run(app)



