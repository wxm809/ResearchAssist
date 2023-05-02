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

def CONNECT():
    return sqlite3.connect('researchassist.db')

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
    print("Putting user")
    connection  = CONNECT()
    cursor = connection.cursor()
    try:
        cursor.execute('INSERT INTO users (id, data) VALUES (?, ?)', (str(user.id), userData))
        connection.commit()
    except sqlite3.IntegrityError:
        raise InsertedExistingUserException
    finally:
        connection.close()

def updateUser(user: User):
    print("updating user")
    userData = pickle.dumps(user)
    connection  = CONNECT()
    cursor = connection.cursor()
    cursor.execute('UPDATE users SET data=? WHERE id=?', (userData, str(user.id)))
    connection.commit()
    connection.close()
    if(cursor.rowcount == 0):
        raise UserNotInDatabaseException

def getUser(id: str) -> User:
    connection = CONNECT()
    cursor = connection.cursor()
    print('in getuser')
    cursor.execute('SELECT data FROM users WHERE id=?', (str(id),))
    response = cursor.fetchone()
    connection.close()
    if response is None:
        raise UserNotInDatabaseException
    return pickle.loads(response[0])

@app.route('/upload', methods=['POST'])
def handleFileUpload():
    print("handling upload")
    id = request.cookies.get('user_id')
    files = request.files.getlist('files')
    subject = request.form['subject']
    try:
        user = getUser(id)
    except UserNotInDatabaseException:
        if not id:
            return newUser()
        else:
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
    return redirect(url_for('conversation', conversation_subject = subject))

def newUser():
    user_id = str(uuid.uuid4())
    try:
        putUser(User(user_id))
    except InsertedExistingUserException:
        return newUser()
    response = make_response(render_template('index.html', conversations = []))
    response.set_cookie('user_id', user_id)
    return response

@app.route('/')
def index():
    user_id = request.cookies.get('user_id')
    print("index", user_id)
    if not user_id:
        return newUser()
    else:
        try:
            user = getUser(user_id)
        except UserNotInDatabaseException:
            return newUser()
        print(user.conversations.keys())
        return render_template('index.html', conversations = user.conversations.keys())

@app.route('/conversation/<conversation_subject>')
def conversation(conversation_subject: str):
    user_id = request.cookies.get('user_id')
    if not user_id:
        return newUser()
    else:
        try:
            user = getUser(user_id)
        except UserNotInDatabaseException:
            return newUser()
        conversation = user.conversations.get(conversation_subject)
        print("conversation page")
        print(user)
        print(user_id)
        print(user.conversations)
        print(conversation)
        print(conversation_subject)
        #print(conversation.documents)
        return render_template("conversation.html", subject = conversation.subject, documents=conversation.documents)
""" 
def ask() -> str:
    id = request.cookies.get('user_id')
    user = getUser(id) #watch out for UserNotInDatabaseException when calling ask!
    conversation = user.conversations.get(request.SOMETHING)
    if conversation is None:
        raise ConversationNotFoundException
    userPrompt = request.SOMETHING_ELSE
    response = "" """

""" def clearDatabase():
    connection = CONNECT()
    cursor = connection.cursor()
    cursor.execute("DROP TABLE users")
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, data BLOB)')
    connection.commit()
    connection.close() """

if __name__ == '__main__':
    connection = CONNECT()
    cursor = connection.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, data BLOB)')
    connection.commit()
    connection.close()
    socketio.run(app, host = "127.0.0.1", port= 6969, debug=True)



