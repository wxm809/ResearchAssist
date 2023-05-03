from flask import Flask, jsonify, request, render_template, redirect, url_for, make_response
import json
import dill as pickle
from classes import User, Conversation
import os
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, send, emit
import uuid
import os
from threading import Thread
import json 
class Thread_(Thread):
    
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs={}):
        Thread.__init__(self, group, target, name, args, kwargs)
        self._return = None

    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args,
                                                **self._kwargs)
    def join(self, *args):
        Thread.join(self, *args)
        return self._return

#import eventlet 
TEMPLATES_PATH = os.path.abspath('templates')
USER_OBJECTS_PATH = os.path.abspath('users')
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

app = Flask(__name__, template_folder = TEMPLATES_PATH)

socketio = SocketIO(app, cors_allowed_origins = '*')#, async_mode = 'eventlet')

def putUser(user: User):
    if(os.path.exists(userPath(user.id))):
        raise InsertedExistingUserException()
    print("Putting user")
    path = userPath(user.id)
    with open(path, 'wb') as f:
        user.dumpUnpickleable()
        pickle.dump(user, f)

def updateUser(user: User):
    print("Upload user")
    path = userPath(user.id)
    with open(path, 'wb') as f:
        user.dumpUnpickleable()
        pickle.dump(user, f)

def getUser(id: str) -> User:
    print('in getuser')
    path = userPath(id)
    print(path)
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
    user.constructGraphFromRequest(subject, files, disable = False)
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
        print(user_id)
        user = getUser(user_id)
        conversation.build()
        conversation_history = conversation.memory.load_memory_variables({})['chat_history'].split('\n')
        return render_template("conversation.html", conversation=conversation, history = conversation_history)
    
@socketio.on('connect')
def handleConnect():
    print('Client connected')
    return None 

@socketio.on('message')
def handleMessage(message):
    print('Message: ' + message.get('text'))
    print('from user: ' + request.cookies.get('user_id'))
    send({'text': message.get('text'), 'from': 'Human'})
    response(message.get('text'), message.get('subject'), request)
    return None

def response(text, subject, request):
    id = request.cookies.get('user_id')
    try:
        user = getUser(id)
    except UserNotInDatabaseException:
        return newUser()
    conversation = user.conversations.get(subject) #this is insanely inefficient but whatever
    if not conversation:
        response = "Sorry, I don't know what you're talking about"
    else:
        conversation.build()
        response = conversation.agentChain.run(input = text)
        updateUser(user)
        emit('response', {'text': response, 'from': 'AI'})
    return None

if __name__ == '__main__':
    #eventlet.monkey_patch()
    socketio.run(app, host = "127.0.0.1", port= 6969, debug=True)


