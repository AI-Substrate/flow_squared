I am giving this context to help you know what we're buildng and why, but don't take this as orders to build all this - its just context on the app and why we're building it. 

Flowspace is an application that does a full AST scan of a codebase using treesitter. It creates a tree of each file - from file -> classes -> methods etc. You can see example of the basics of this in /workspaces/flow_squared/docs/plans/001-universal-ast-parser and /workspaces/flow_squared/initial_exploration. 

Our first inital scan will iterate though all files that treesitter supports - md files, python, terraform, dockerfiles ... everything! Even yaml, but it hsould have a size cap! if its too large, then it will just sample top section. 

It should also obey .gitignore. 

The system will take a simple config - 
scan_paths:
    - "./docs"
    - "./initial_exploration". 

    You will need to understand the curent config systme nad get the proper python objects etc set up to support this. 

Later the system will generate LLM Summaries of each thing - entire file, entire class and entire method (even if there is repeats), then it will also create embeddings for original content nad smart content. 

All this will be saved in a networkx graph that can be very quickly scanned. Why networkx? Later we will add in method to method calls and other refgerence relationships lie in the original version of flowspace. But for now, we just need to scan the files, "AST" them in to the components as we discussed in 001 plan, and store them in the graph as a heirarchy of nodes (file is top node, then what even children will be edges and so on to build the heirarchy. )

We will need a good data object that we can use to represent these elements. They should be the same (type: file, type:method etc...) There iwll not be a file type or a method type in our object model, the reason is we will be supporting so much variion in file types. THe main thing is we can see the line numbers, the smart content, the embeddings etc.

OOS right now is creating smart content or embeddings. We just want to get the basics of hte AST parser in, and create a very basic hierarchy. There will be no rels between elements in differnt files (or even elements in same file unless its from the base hierarchy - file to class etc... but not method to method.)

We will need a service to control the graph, another one ot scan the files, antoher one to ast them etc... we want SRP, ensure you study the clean architecutre of the system properly. 

We will need the CLI to enable a "scan" which will create the graph. 

KISS and YAGNI are our goals here... do no over engineer. 