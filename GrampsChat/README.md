GrampsChat addon Gramplet is a configurable Chatbot conversation plugin that is compatible with Gramps 6.0 for desktops. It can be used with commercial LLM providers (like OpenAI) or with your own LLM server.

* An LLM (Large Language Model) is a type of artificial intelligence model trained on a massive amount of text data. It's designed to understand and generate human-like text.
* A chatbot is an interface that lets you "discuss" what you want the software to do, instead of being limited to rigidly pre-defined options in a traditional windows, icons, menus, and pointer interface. You interact by typing questions or requests using everyday language. The chatbot uses an LLM (Large Language Model) to figure out what you meant and generate a relevant response. It's designed to simulate a conversation, acting as a digital assistant to answer questions or assist with tasks through natural dialogue.

The GrampsChat gramplet integrates a chatbot interface into Gramps.

Here's the core functionality it provides:
* Chat Interface: It adds a text-based area within Gramps where you can ask questions and receive responses.
* AI Model Connection: It uses the litellm library to connect to various AI models (like OpenAI's GPT or open-source models). You'll need to configure it to point to the AI model you want to use, typically with an API key.
* Environment Configuration: The gramplet requires configuration via environment variables. These variables tell it which AI model to use and how to connect. The gramplet provides instructions for setting these up.
* Conversation History: It remembers the chat history to give the AI context for better answers. You can start a new conversation to clear the history.
* Asynchronous Operation: The gramplet handles the AI interaction in the background so Gramps remains responsive.
* Message Formatting: The gramplet formats user and AI messages differently for clarity.
* Opik Integration (Optional): If configured with an OPIK_API_KEY, it logs conversations to Comet's Opik for tracking and analysis.  **Full disclosure:** Opik is an open source LLM tracking and evaluation tool created by the devloper's employer. (Comet ML)

In essence: GrampsChat provides a framework for interfacing with a conversational AI within Gramps. Its primary role is to connect you to an external AI service and display the conversation in a Gramps window.

Keep in mind: You'll need to configure it with an AI model and any necessary API keys to get it working.

The Windows and Linux versions of the Addon Manager will us pip to automatically install the required `litellm' module, if the "Allow Gramps to install required Python modules" settings option is set appropriately. 
The macOS version Installation of the required module must be done manually.   

See
* Gramps community forum : [GrampsChat addon for 6.0](https://gramps.discourse.group/t/grampschat-addon-for-6-0/7108)
* Initial Gramps addons-source repository Pull Request : [PR654](https://github.com/gramps-project/addons-source/pull/654#issue-2867079969) Added GrampsChat
