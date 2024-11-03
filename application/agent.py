from typing import TypedDict, Annotated
from langchain_core.agents import AgentAction
from langchain_core.messages import BaseMessage
import operator
from langchain_core.tools import tool
from serpapi import GoogleSearch
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolCall, ToolMessage
from langchain_openai import ChatOpenAI
from typing import TypedDict
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
   input: str
   chat_history: list[BaseMessage]
   intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]

@tool("product_search")
def product_search(query: str):
   """Finds general knowledge information using Google search. Can also be used
   to augment more 'general' knowledge to a previous specialist query. """
   search = GoogleSearch({
       "engine": "google",
       "api_key":  "", # your serpapi api key
       "q": query,
       "num": 5
   })
   results = search.get_dict()["organic_results"]
   contexts = "\n---\n".join(
       ["\n".join([x["title"], x["snippet"], x["link"]]) for x in results]
   )
   return contexts

@tool("final_answer")
def final_answer(
   ingredients: str,
   allergens: str,
   harmful_ingredients: str,
   conclusion: str,
   sources: str
):
   """Returns a natural language response to the user explaining the ingredients and chemical present in the product and any allergen information and harmful effects if any of those chemicals and ingredients. There are several sections to this report, those are:
   - `Ingredients`: List of major ingredients.
   - `Allergens`: Highlight any allergens present in the product.
   - `Harmful Ingredients`: list harmful ingredients and their effects.
   - `conclusion`: this is a short single paragraph conclusion providing a
   concise but sophisticated view on what was found.
   - `sources`: a bullet point list provided detailed sources for all information
   referenced during the research process
   """
   if type(ingredients) is list:
      ingredients = "\n".join([f"- {r}" for r in ingredients])
   if type(harmful_ingredients) is list:
      allergens = "\n".join([f"- {r}" for r in harmful_ingredients])
   if type(allergens) is list:
      allergens = "\n".join([f"- {r}" for r in allergens])
   if type(sources) is list:
      sources = "\n".join([f"- {s}" for s in sources])

   return ""

system_prompt = """You are the oracle, the great AI decision maker.
Given the user's query you must identify the product and its brand from the user query and then you should use the tools available to you to find the ingredients and chemical which are presents in the product.
Then you should search for any allergen information and harmful effects if any for the chemicals and ingredients of the product. You should then summarize your finding ina report formate.There are several sections to this report, those are:

If you see that a tool has been used (in the scratchpad) with a particular
query, do NOT use that same tool with the same query again. Also, do NOT use
any tool more than four time (ie, if the tool appears in the scratchpad 4 times, do
not use it again).

Once you have collected information
to answer the user's question (stored in the scratchpad) use the final_answer
tool."""

prompt = ChatPromptTemplate.from_messages([
   ("system", system_prompt),
   MessagesPlaceholder(variable_name="chat_history"),
   ("user", "{input}"),
   ("assistant", "scratchpad: {scratchpad}"),
])


llm = ChatOpenAI(
   model="gpt-4o",
   openai_api_key="", # your openai api key
   temperature=0
)

tools=[
   product_search,
   final_answer
]

def create_scratchpad(intermediate_steps: list[AgentAction]):
   research_steps = []
   for i, action in enumerate(intermediate_steps):
       if action.log != "TBD":
           # this was the ToolExecution
           research_steps.append(
               f"Tool: {action.tool}, input: {action.tool_input}\n"
               f"Output: {action.log}"
           )
   return "\n---\n".join(research_steps)


oracle = (
   {
       "input": lambda x: x["input"],
       "chat_history": lambda x: x["chat_history"],
       "scratchpad": lambda x: create_scratchpad(
           intermediate_steps=x["intermediate_steps"]
       ),
   }
   | prompt
   | llm.bind_tools(tools, tool_choice="auto")
)

def run_oracle(state: TypedDict):
   out = oracle.invoke(state)
   tool_name = out.tool_calls[0]["name"]
   tool_args = out.tool_calls[0]["args"]
   action_out = AgentAction(
       tool=tool_name,
       tool_input=tool_args,
       log="TBD"
   )
   return {
       "intermediate_steps": [action_out]
   }


def router(state: TypedDict):
   # return the tool name to use
   if isinstance(state["intermediate_steps"], list):
       return state["intermediate_steps"][-1].tool
   else:
       # if we output bad format go to final answer
       return "final_answer"
   

tool_str_to_func = {
   "product_search": product_search,
   "final_answer": final_answer,

}


def run_tool(state: TypedDict):
   tool_name = state["intermediate_steps"][-1].tool
   tool_args = state["intermediate_steps"][-1].tool_input
   # run tool
   out = tool_str_to_func[tool_name].invoke(input=tool_args)
   action_out = AgentAction(
       tool=tool_name,
       tool_input=tool_args,
       log=str(out)
   )
   return {"intermediate_steps": [action_out]}


graph = StateGraph(AgentState)
graph.add_node("oracle", run_oracle)
graph.add_node("product_search", run_tool)
graph.add_node("final_answer", run_tool)
graph.set_entry_point("oracle")
graph.add_edge("final_answer", END)
graph.add_conditional_edges(
   source="oracle",  # where in graph to start
   path=router,  # function to determine which node is called
)
for tool_obj in tools:
   if tool_obj.name != "final_answer":
       graph.add_edge(tool_obj.name, "oracle")
graph.add_edge("final_answer", END)
runnable = graph.compile()


def get_product_info(user_query: str):
    state = {
        "input": user_query,
        "chat_history": [],
    }
    output =  runnable.invoke(state)["intermediate_steps"][-1].tool_input
    
    product_info ={}
    for key, value in output.items():
        product_info[key] = value
    
    return product_info