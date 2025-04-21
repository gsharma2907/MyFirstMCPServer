**Building my First MCP Server**
(**And the fun of vibe coding**)

There is so much hype about Anthropic's Model Context Protocol(MCP) Server for last few days and today I tried to build my own. But first let's understand what is MCP and why was it needed.

Let's take an example, my organization is building an enterprise chatbot for the internal users and want to provide them answers from various data sources such as a data warehouse or a document repository or few internal or external websites. We also want our end users to be able to create internal tickets for departments like HR or Finance and for that our application needs to talk to an internal ticketing tool as well. Traditionally my developer would have to know different APIs for these tools and include them in the AI application and build subsequent agentic workflow. Building , maintaining or troubleshooting this code was becoming nightmare for the developers. 

Think of MCP Servers as the middleware with a standard and open API specification which talks to various different tools or databases or data repositories and get the required data to your client or AI application. How does it help ? Now the same developer using MCP servers for each tool or data store will just have to learn and use the MCP API specification in building its Agentic AI workflow. The tool specific API and data retrieval logic is left to MCP servers. 

In an effort to learn and build a simplistic MCP Server myself , I built a document search chatbot which looks for my documents in google drive, gmail, my outlook or my local folders. 

PS: Almost all the code was generated using LLMs. 
