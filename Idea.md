Idea;

Landing page: upload pdfs of an abritrary number of research papers, with a maximum of 20,000 words. GPT will read them.
-For each article, generate an internal summary that reduces the number of tokens it takes up. Have a page number for each bullet point
    -Probably need to use token hack subroutine (https://blog.devgenius.io/how-to-get-around-openai-gpt-3-token-limits-b11583691b32)
-Maintain the internal summaries in a database for model to consult later. Use some classification algorithm to dynamically consult this database in conversation. Cite the page number for each answer
-Have an option for GPT to give you detailed information about a certain question. Consult the page number in the original document
-Use LLamaIndex to store the PDFs
-Also feed it the wikipedia page of the field it is consulting
Slider to configure detail level of summaries.

Next page: 
Cells for each of the articles. Each article will have a summary. 
Below the articles, chatbox. You can chat with GPT about the articles and ask it other related (or unrelated) questions. 
