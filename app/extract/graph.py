from __future__ import annotations

import enum
from typing import List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.vectorstores import VectorStore
from langgraph.graph import END, StateGraph

from app.extract.retrieval import retrieve
from app.metadata.base import Strategy
from app.metadata.schemas import ProposedMetadata


class RouteEnum(enum.Enum):
    OK = 'OK'
    RETRY = 'RETRY'
    FAIL = 'FAIL'


class ExtractState(TypedDict, total=False):
    digest: str
    collection: Optional[str]  # if you want to route to a specific collection
    query: str  # retrieval query
    docs: List[Document]
    metadata: ProposedMetadata
    score: float
    detail: dict
    attempt: int
    max_attempts: int
    route: RouteEnum


def _search_params(attempt: int) -> dict:
    return {
        '1': {'search_type': 'similarity', 'k': 6},
        '2': {'search_type': 'mmr', 'k': 8, 'fetch_k': 32, 'lambda_mult': 0.5},
        '3': {
            'search_type': 'similarity_score_threshold',
            'k': 12,
            'score_threshold': 0.3,
        },
    }[str(attempt)]


def make_retrieve_node(vs: VectorStore) -> RunnableLambda:
    async def _retrieve(state: ExtractState) -> ExtractState:
        # If we are coming back from a RETRY route, bump the attempt counter
        if state.get('route') == RouteEnum.RETRY:
            state['attempt'] = min(state.get('attempt', 1) + 1, state.get('max_attempts', 3))
        params = _search_params(state.get('attempt', 1))
        state['docs'] = await retrieve(
            vs,
            query=state['query'],
            digest=state['digest'],
            **params,
        )
        return state

    return RunnableLambda(_retrieve)


def make_extract_node(llm: BaseChatModel, strategy: Strategy) -> RunnableLambda:
    async def _extract(state: ExtractState) -> ExtractState:
        if not state.get('docs'):
            # Ensure callers always see a structured payload with the expected keys
            # even when no documents could be retrieved.
            state['metadata'] = ProposedMetadata(metadata={'metadata': {}, 'evidence': {}})
            return state

        context = strategy.make_context(state['docs'])
        schema = strategy.build_llm_response_model()
        prompt = ChatPromptTemplate.from_messages(
            [
                ('system', strategy.system_prompt()),
                ('user', strategy.user_prompt(context)),
            ]
        )

        chain = prompt | llm.with_structured_output(schema)
        llm_result = await chain.ainvoke({})
        if not isinstance(llm_result, schema):
            raise ValueError(f'Invalid LLM response: {llm_result}')

        state['metadata'] = ProposedMetadata(metadata=llm_result.model_dump())
        return state

    return RunnableLambda(_extract)


def make_assess_node(strategy: Strategy) -> RunnableLambda:
    async def _assess(state: ExtractState) -> ExtractState:
        result = strategy.assess_quality(metadata=state['metadata'], docs=state['docs'])
        state['score'] = result.score
        state['detail'] = result.details

        if result.score >= 0.75:
            state['route'] = RouteEnum.OK
        else:
            state['route'] = (
                RouteEnum.RETRY if state.get('attempt', 1) < state.get('max_attempts', 3) else RouteEnum.FAIL
            )
        return state

    return RunnableLambda(_assess)


# Router edge selector (LangGraph "routing" pattern).  [oai_citation:6‡LangChain AI](https://langchain-ai.github.io/langgraph/tutorials/workflows/?utm_source=chatgpt.com)
def route_fn(state: ExtractState) -> RouteEnum:
    return state.get('route', RouteEnum.FAIL)


def build_extract_graph(vs: VectorStore, llm: BaseChatModel, strategy: Strategy):
    g = StateGraph(ExtractState)

    g.add_node('retrieve', make_retrieve_node(vs))
    g.add_node('extract', make_extract_node(llm, strategy))
    g.add_node('assess', make_assess_node(strategy))

    # default entry
    g.set_entry_point('retrieve')

    # retrieve → extract → assess
    g.add_edge('retrieve', 'extract')
    g.add_edge('extract', 'assess')

    # conditional routing
    g.add_conditional_edges(
        'assess',
        route_fn,
        {
            RouteEnum.OK: END,
            RouteEnum.RETRY: 'retrieve',
            RouteEnum.FAIL: END,
        },
    )

    return g.compile()
