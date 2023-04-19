import os
import OpenAI
from llama_index import Document, GPTSimpleVectorIndex, SimpleNodeParser
from multiprocessing import Process
from flask import Flask, jsonify, request, render_template
import json

app = Flask(__name__)
app.debug(True)

@app.route('/upload', methods=['POST'])
def upload():
    documents = [Document(t) for t in request.files.getlist('pdfs')] #get pdfs from request and read them into a list of Documents
    index = GPTSimpleVectorIndex(SimpleNodeParser().get_nodes_from_documents(documents)) #create index from documents


