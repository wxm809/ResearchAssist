from langchain import OpenAI
from langchain.agents import Tool, initialize_agent
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI


from llama_index import Document, GPTSimpleVectorIndex, LLMPredictor, PromptHelper, ServiceContext, GPTListIndex
from llama_index.indices.composability import ComposableGraph
from llama_index.langchain_helpers.agents import LlamaToolkit, create_llama_chat_agent, IndexToolConfig, GraphToolConfig
from llama_index.indices.query.query_transform.base import DecomposeQueryTransform

maxInputSize = 4096
maxOutput = 2000
maxChunkOverlap=20
PROMPT_HELPER = PromptHelper(maxInputSize, maxOutput, maxChunkOverlap)
PREDICTOR = LLMPredictor(llm = OpenAI(temperature = 0.2, model_name = 'gpt-3.5-turbo', max_tokens=maxOutput))



class Conversation:
    def __init__(self, subject: str, graph: ComposableGraph, indices: dict):
        self.graph = graph
        self.subject = subject
        self.indices = indices
        self.toolkit = self.makeToolkit(graph, indices)
        self.memory = ConversationBufferMemory(memory_key = "chat_history")
        self.agent_chain = create_llama_chat_agent(
            self.toolkit,
            OpenAI(temperature = 0.2, model_name = 'gpt-3.5-turbo', max_tokens=maxOutput),
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
            query_configs=query_configs,
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
    def __init__(self, id: int):
        self.id = id 
        self.conversations = {}
    def constructGraphFromRequest(self, request: request) -> GPTSimpleVectorIndex:
        if(request.files.getlist('pdfs') == []):
            return None
        documents = [Document(t) for t in request.files.getlist('pdfs')] #get pdfs from request and read them into a list of Documents
        indices = {}
        serviceContext = ServiceContext.from_defaults(llm_predictor = PREDICTOR, prompt_helper=PROMPT_HELPER)
        for document in documents:
            title = 'PLACEHOLDER: ARTICLE TITLE. USE REQUEST'
            document.extra_info = title
            indices[title] = GPTSimpleVectorIndex(document, serviceContext)
        indexSummaries = [summarize(index) for index in indices.values()] #TODO: Write summarize
        graph = ComposableGraph.from_indices(
            GPTListIndex,
            indices.values(),
            index_summaries = indexSummaries,
            service_context = serviceContext
        ) #create graph from indices
        self.conversations.put(request.SOMETHING, Conversation(request.SOMETHIGNG_ELSE, graph, indices)) #TODO: MAKE CONVERSATION ID DEPEND ON COOKIES 
        return graph
