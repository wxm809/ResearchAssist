from flask import Flask, jsonify, request, render_template, redirect, url_for, make_response
import json
import pickle
from classes import User, Conversation
from llama_index import GPTSimpleVectorIndex
import os
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
import uuid
import os

USER_OBJECTS_PATH = 'users'
print(os.getcwd())
if not os.path.exists(USER_OBJECTS_PATH):
    os.makedirs(USER_OBJECTS_PATH)

class InsertedExistingUserException(Exception):
    pass

class UserNotInDatabaseException(Exception):
    pass

class ConversationNotFoundException(Exception):
    pass

def userPath(user_id: str) -> str:
    return os.path.join(USER_OBJECTS_PATH, f"{user_id}.pkl")

app = Flask(__name__)

socketio = SocketIO(app)

def putUser(user: User):
    if(os.path.exists(userPath(user.id))):
        raise InsertedExistingUserException()
    print("Putting user")
    path = userPath(user.id)
    with open(path, 'wb') as f:
        pickle.dump(user, f)

def updateUser(user: User):
    print("Upload user")
    path = userPath(user.id)
    with open(path, 'wb') as f:
        pickle.dump(user, f)

def getUser(id: str) -> User:
    print('in getuser')
    path = userPath(id)
    if not os.path.exists(path):
        raise UserNotInDatabaseException
    with open (path, 'rb') as f:
        user = pickle.load(f)
    return user

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
        if not file or not file.filename.endswith('.pdf'):
            files.remove(file)
    if(len(files) == 0):
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
    print(os.getcwd())
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

if __name__ == '__main__':
    socketio.run(app, host = "127.0.0.1", port= 6969, debug=True)


