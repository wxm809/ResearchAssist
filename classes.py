from langchain.chat_models import ChatOpenAI
from langchain.agents import Tool, initialize_agent
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI

from flask import Flask, jsonify, request, render_template
from werkzeug.datastructures import FileStorage
import PyPDF2
from io import BytesIO

from llama_index import Document, GPTSimpleVectorIndex, LLMPredictor, PromptHelper, ServiceContext, GPTListIndex
from llama_index.indices.composability import ComposableGraph
from llama_index.langchain_helpers.agents import LlamaToolkit, create_llama_chat_agent, IndexToolConfig, GraphToolConfig
from llama_index.indices.query.query_transform.base import DecomposeQueryTransform

maxInputSize = 4096
maxOutput = 2000
maxChunkOverlap=20
PROMPT_HELPER = PromptHelper(maxInputSize, maxOutput, maxChunkOverlap)
PREDICTOR = LLMPredictor(llm = ChatOpenAI(temperature = 0.2, model_name = 'gpt-3.5-turbo', max_tokens=maxOutput))



class Conversation:
    def __init__(self, subject: str, graph: ComposableGraph, indices: dict, documents: list, disable: bool = False):
        self.documents = documents
        self.subject = subject
        if not disable:
            self.graph = graph
            self.indices = indices
            self.toolkit = self.makeToolkit(graph, indices)
            self.memory = ConversationBufferMemory(memory_key = "chat_history")
            self.agent_chain = create_llama_chat_agent(
                self.toolkit,
                ChatOpenAI(temperature = 0.2, model_name = 'gpt-3.5-turbo', max_tokens=maxOutput),
                memory=self.memory,
                verbose=True
            )
        
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
        graph_config = GraphToolConfig(
            graph=graph,
            name=f"Graph Index",
            description="useful for when you want to answer queries that require analyzing multiple papers.",
            query_configs=QUERY_CONFIG,
            tool_kwargs={"return_direct": True}
        )
        index_configs = []
        for title in self.indices.keys():
            tool_config = IndexToolConfig(
            index=self.indices[title], 
            name=f"Vector Index {title}",
            description=f"useful for when you want to answer queries about the paper {title}",
            index_query_kwargs={"similarity_top_k": 3},
            tool_kwargs={"return_direct": True}
            )
            self.index_configs.append(tool_config)
        return LlamaToolkit(
            index_configs=index_configs,
            graph_configs=[graph_config]
        )

class User:
    def __init__(self, id: str):
        self.id = str(id) 
        self.conversations = {}
    def constructGraphFromRequest(self, subject:str, files: list, disable: bool = False) -> GPTSimpleVectorIndex:
        if files == [] or files is None:
            return None
        #Extract text from pdfs
        contents = [t.stream.read() for t in files] 
        file_streams = BytesIO(contents)
        pdf_contents = []
        for file in file_streams:
            reader = PyPDF2.PdfFileReader(file)
            for page in range(reader.getNumPages()):
                text += reader.getPage(page).extractText()
            pdf_contents.append(text)

        #Make Documents from the PDF contents
        documents = [Document(t) for t in pdf_contents]
        if not disable:
            #Make indices from the documents
            indices = {}
            serviceContext = ServiceContext.from_defaults(llm_predictor = PREDICTOR, prompt_helper=PROMPT_HELPER)
            for i, document in enumerate(documents):
                title = files[i].filename
                document.extra_info = title
                indices[title] = GPTSimpleVectorIndex(document, serviceContext)
            indexSummaries = [summarize(index) for index in indices.values()] #TODO: Write summarize
            graph = ComposableGraph.from_indices(
                GPTListIndex,
                indices.values(),
                index_summaries = indexSummaries,
                service_context = serviceContext
            ) #create graph from indices
        self.conversations.put(subject, Conversation(subject, graph, indices, documents, disable = disable)) #TODO: MAKE CONVERSATION ID DEPEND ON COOKIES 
        return graph

def summarize(index: GPTSimpleVectorIndex) -> str:
    return "PLACEHOLDER: WRITE SUMMARY"