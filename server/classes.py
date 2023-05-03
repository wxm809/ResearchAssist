from langchain.chat_models import ChatOpenAI
from langchain.agents import Tool, initialize_agent
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.chat_models import ChatOpenAI

from flask import Flask, jsonify, request, render_template
from werkzeug.datastructures import FileStorage
import PyPDF2
from io import BytesIO
import os 
from llama_index import Document, GPTVectorStoreIndex, LLMPredictor, PromptHelper,load_graph_from_storage
from llama_index import load_index_from_storage,  ServiceContext, StorageContext, GPTListIndex
from llama_index.indices.composability import ComposableGraph
from llama_index.langchain_helpers.agents import LlamaToolkit, create_llama_chat_agent, IndexToolConfig
from llama_index.indices.query.query_transform.base import DecomposeQueryTransform
from llama_index.query_engine.transform_query_engine import TransformQueryEngine

maxInputSize = 4096
maxOutput = 2000
maxChunkOverlap=20
PROMPT_HELPER = PromptHelper(maxInputSize, maxOutput, maxChunkOverlap)
PREDICTOR = LLMPredictor(llm = ChatOpenAI(temperature = 0.2, model_name = 'gpt-3.5-turbo', max_tokens=maxOutput))

USER_OBJECTS_PATH = os.path.abspath('users')
print(os.getcwd())
if not os.path.exists(USER_OBJECTS_PATH):
    os.makedirs(USER_OBJECTS_PATH)

def indexPath(user_id: str, index: str) -> str:
    return os.path.join(USER_OBJECTS_PATH, f"{user_id}.{index}")

class Conversation:
    def __init__(self, subject: str, documents: list, user_id: str):
        self.user_id = user_id
        self.documents = documents
        self.subject = subject            
        self.memory = ConversationBufferWindowMemory(memory_key = "chat_history", k = 30)
        indices = {}
        serviceContext = ServiceContext.from_defaults(llm_predictor = PREDICTOR, prompt_helper=PROMPT_HELPER)
        for document in self.documents:
            storageContext = StorageContext.from_defaults()
            indices[document.extra_info['title']] = GPTVectorStoreIndex.from_documents(
                [document], 
                service_context = serviceContext, storage_context = storageContext)
            storageContext.persist(persist_dir= indexPath(user_id, document.extra_info['title']))
        storageContext = StorageContext.from_defaults()
        graph = ComposableGraph.from_indices(
            GPTListIndex,
            list(indices.values()),
            index_summaries = [summarize(index) for index in indices.values()],
            service_context = serviceContext,
            storage_context=storageContext,
        ) #create graph from indices
        self.indices = indices
        self.graph = graph
        self.graph_root_id = graph.root_id
        storageContext.persist(persist_dir= indexPath(user_id, graph.root_id))
            
    def build(self):
        indices = {}
        for document in self.documents:
            storageContext = StorageContext.from_defaults(persist_dir= indexPath(self.user_id, document.extra_info['title']))
            indices[document.extra_info['title']] = load_index_from_storage(storage_context=storageContext)
        self.indices = indices
        serviceContext = ServiceContext.from_defaults(llm_predictor = PREDICTOR, prompt_helper=PROMPT_HELPER)
        self.graph = load_graph_from_storage(
            root_id = self.graph_root_id,
            service_context = serviceContext,
            storage_context=StorageContext.from_defaults(persist_dir= indexPath(self.user_id, self.graph_root_id)),
        )
        self.toolkit = self.makeToolkit(self.graph, self.indices)
        self.agentChain = create_llama_chat_agent(
            self.toolkit,
            ChatOpenAI(temperature = 0.2, model_name = 'gpt-3.5-turbo', max_tokens=maxOutput),
            memory=self.memory,
            verbose=True
        )

    def dumpUnpickleable(self):
        self.graph = None
        self.indices = None
        self.toolkit = None
        self.agentChain = None
  
    def makeToolkit(self, graph: ComposableGraph, indices: dict) -> LlamaToolkit:
        decompose_transform = DecomposeQueryTransform(PREDICTOR, verbose=True)
        # define query configs for graph 
        QUERY_CONFIG = [
            {
                "index_struct_type": "simple_dict",
                "query_mode": "default",
                "query_kwargs": {
                    "similarity_top_k": 1,
                    # "include_summary": True
                },
                "query_transform": decompose_transform
            },
            {
                "index_struct_type": "list",
                "query_mode": "default",
                "query_kwargs": {
                    "response_mode": "tree_summarize",
                    "verbose": True
                }
            },
        ]

        custom_query_engines = {}
        for index in indices.values():
            query_engine = index.as_query_engine()
            query_engine = TransformQueryEngine(
                query_engine,
                query_transform=decompose_transform,
                transform_extra_info={'index_summary': index.index_struct.summary},
            )
            custom_query_engines[index.index_id] = query_engine
        custom_query_engines[graph.root_id] = graph.root_index.as_query_engine(
            response_mode='tree_summarize',
            verbose=True,
        )

        graph_config = IndexToolConfig(
            query_engine = query_engine,
            name=f"Graph Index",
            description="useful if you need to answer queries that require analyzing multiple papers.",
            query_configs=QUERY_CONFIG,
            tool_kwargs={"return_direct": True},
        )
        index_configs = []
        for title in self.indices.keys():
            query_engine = indices[title].as_query_engine(similarity_top_k=3)
            tool_config = IndexToolConfig(
                query_engine = query_engine,
                name=f"Vector Index {title}",
                description=f"useful if you need to answer queries about the paper {title} or subjects related to it.",
                index_query_kwargs={"similarity_top_k": 3},
                tool_kwargs={"return_direct": True}
            )
            index_configs.append(tool_config)
        return LlamaToolkit(
            index_configs=index_configs + [graph_config]
        )

class User:
    def __init__(self, id: str):
        self.id = str(id) 
        self.conversations = {}
    def constructGraphFromRequest(self, subject:str, files: list, disable: bool = False) -> GPTVectorStoreIndex:
        if files == [] or files is None:
            return None
        #Extract text from pdfs
        contents = [t.stream.read() for t in files] 
        file_streams = [BytesIO(content) for content in contents]
        pdf_contents = []
        for file in file_streams:
            reader = PyPDF2.PdfReader(file)
            text= ""
            for page in range(len(reader.pages)):
                text += reader.pages[page].extract_text()
            pdf_contents.append(text)

        #Make Documents from the PDF contents
        documents = [Document(t) for t in pdf_contents]
        for i, document in enumerate(documents):
            document.extra_info = {"title": os.path.splitext(files[i].filename)[0]}
        self.conversations[subject] = Conversation(subject, documents, self.id) 
    
    def dumpUnpickleable(self):
        for conversation in self.conversations.values():
            conversation.dumpUnpickleable()

def summarize(index: GPTVectorStoreIndex) -> str:
    queryEngine = index.as_query_engine(response_mode = "tree_summarize")
    response = queryEngine.query('summarize')
    print(response)
    return response